import fastapi
import requests
from pydantic import BaseModel, Field
import os
import uvicorn
import threading
import time
from typing import List

app = fastapi.FastAPI()

# --- Variáveis Globais ---
message_queue = []
queue_lock = threading.Lock() # Lock para garantir acesso thread-safe à fila
acks_received = {} # Dicionário para rastrear ACKs: {(origin_id, timestamp): {ack_source_1, ...}}
internal_clock = 0 # Relógio lógico de Lamport
process_id = int(os.getenv("PROCESS_ID", "1"))
all_processes = [1, 2, 3] # IDs de todos os processos no sistema

# --- Modelos Pydantic ---
class Message(BaseModel):
    data: str
    origin_id: int
    timestamp: int

    def verify_acks(self):
        '''Retorna True caso tenha recebido ACKs de todos os servidores'''
        # A verificação agora usa o dicionário global de acks
        # Um processo não envia ACK para si mesmo, então adicionamos seu próprio ID para a verificação
        global acks_received
        acknowledged_by = acks_received.get((self.origin_id, self.timestamp), set())
        global process_id
        acknowledged_by.add(process_id)
        return acknowledged_by == set(all_processes)

class Ack(BaseModel):
    message_origin_id: int
    message_timestamp: int
    ack_origin_id: int

# --- Funções de Broadcast ---

def broadcast_message(message: Message):
    '''Envia a mensagem para os outro processos'''
    for process in all_processes:
        if process != process_id:
            try:
                # O endpoint para receber mensagens de outros processos
                url = f"http://app-{process}:8000/recieve_message"
                requests.post(url, json=message.model_dump(), timeout=0.5)
            except Exception as e:
                print(f"ERROR: Falha ao enviar mensagem para o processo {process}: {e}")


def broadcast_ack(original_message: Message):
    '''Envia ACK de uma mensagem a todos os outros processos'''
    global process_id
    ack_message = Ack(
        message_origin_id=original_message.origin_id,
        message_timestamp=original_message.timestamp,
        ack_origin_id=process_id
    )
    for process in all_processes:
        if process != process_id:
            try:
                url = f"http://app-{process}:8000/recieve_ack"
                requests.post(url, json=ack_message.model_dump(), timeout=0.5)
            except Exception as e:
                print(f"ERROR: Falha ao enviar ACK para o processo {process}: {e}")

# --- Endpoints da API ---

@app.post('/recieve_external_message')
def recieve_external_message(message: str):
    '''Recebe uma mensagem de um cliente externo e inicia o multicast'''
    print(f"DEBUG: Process {process_id} received external message: '{message}'")
    global internal_clock
    internal_clock += 1
    with queue_lock:
        new_message = Message(data=message, origin_id=process_id, timestamp=internal_clock)
        print(f"DEBUG: Process {process_id} created new message: {new_message.model_dump_json()}")
        message_queue.append(new_message)
        message_queue.sort(key=lambda m: (m.timestamp))
    broadcast_message(new_message) # Broadcast fora do lock para não bloquear por I/O
    return 


@app.post('/recieve_message')
def recieve_message(message: Message):
    '''Recebe uma mensagem de outro processo'''
    print(f"DEBUG: Process {process_id} received message from process {message.origin_id} with timestamp {message.timestamp}")
    global internal_clock
    internal_clock = max(internal_clock, message.timestamp) + 1

    message_key = (message.origin_id, message.timestamp)
    with queue_lock:
        # Inicializa o rastreamento de ACKs para esta mensagem
        # O remetente original e o processo atual são os primeiros a "confirmar"
        if message_key not in acks_received:
            acks_received[message_key] = set()

        acks_received[message_key].add(message.origin_id)
        message_queue.append(message)
        message_queue.sort(key=lambda m: (m.timestamp))
    # Envia ACK para todos os outros processos
    print(f"DEBUG: Process {process_id} broadcasting ACK for message from {message.origin_id} with timestamp {message.timestamp}")
    broadcast_ack(message)
    return 
        
@app.post('/recieve_ack')
def recieve_ack(ack: Ack):
    '''Recebe um ACK de outro processo'''
    print(f"DEBUG: Process {process_id} received ACK from {ack.ack_origin_id} for message ({ack.message_origin_id}, {ack.message_timestamp})")
    # Encontra a mensagem na fila que corresponde ao ACK
    message_key = (ack.message_origin_id, ack.message_timestamp)
    with queue_lock:
        # Garante que a entrada para esta mensagem exista no dicionário de ACKs.
        if message_key not in acks_received:
            acks_received[message_key] = set()
        # Adiciona o ACK. Esta operação é O(1) e funciona mesmo se a mensagem ainda não chegou.
        acks_received[message_key].add(ack.ack_origin_id)
        print(f"DEBUG: Process {process_id} updated ACKs for message {message_key}. New acks: {acks_received[message_key]}")
    return 

# --- Lógica de Entrega de Mensagens ---

def deliver_messages():
    '''Verifica a fila e entrega as mensagens que receberam todos os ACKs em ordem'''
    while True:
        delivered_message = None
        with queue_lock:
            # A verificação e o pop() agora são uma operação atômica
            if message_queue and message_queue[0].verify_acks():
                delivered_message = message_queue.pop(0)
                # Limpa a entrada de ACKs para a mensagem entregue para não consumir memória
                if delivered_message:
                    acks_received.pop((delivered_message.origin_id, delivered_message.timestamp), None)
        
        if delivered_message:
            # Acessar delivered_message fora do lock para não segurá-lo durante o print
            print(f"DELIVERED: '{delivered_message.data}' from process {delivered_message.origin_id} with timestamp {delivered_message.timestamp}")
        else: # Só checar a cabeça da fila se nada foi entregue
            with queue_lock:
                if message_queue and (message_queue[0].origin_id, message_queue[0].timestamp) in acks_received:
                    print(f"DEBUG: Process {process_id} waiting for ACKs for message ({message_queue[0].origin_id}, {message_queue[0].timestamp}). ACKs already received: {acks_received.get((message_queue[0].origin_id, message_queue[0].timestamp))}")
        time.sleep(1)

if __name__ == "__main__":
    # Inicialização do processo
    internal_clock = 5 * process_id
    
    # Inicia a thread para entrega de mensagens
    delivery_thread = threading.Thread(target=deliver_messages, daemon=True)
    delivery_thread.start()
    
    print(f"Processo {process_id} iniciado.")
    uvicorn.run(app, host="0.0.0.0", port=8000)