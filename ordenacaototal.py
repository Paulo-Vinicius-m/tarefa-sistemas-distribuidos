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
internal_clock = 0 # Relógio lógico de Lamport
process_id = int(os.getenv("PROCESS_ID", "0"))
all_processes = [1, 2, 3] # IDs de todos os processos no sistema

# --- Modelos Pydantic ---

class Message(BaseModel):
    data: str
    process_id: int
    timestamp: int
    acks_sources: List[int] = Field(default_factory=list)

    def verify_acks(self):
        '''Retorna True caso tenha recebido ACKs de todos os servidores'''
        # Um processo não envia ACK para si mesmo, então adicionamos seu próprio ID para a verificação
        acknowledged_by = set(self.acks_sources + [self.process_id])
        return acknowledged_by == set(all_processes)

class Ack(BaseModel):
    message_process_id: int
    message_timestamp: int
    ack_source_process_id: int

# --- Funções de Broadcast ---

def broadcast_message(message: Message):
    '''Envia a mensagem para os outro processos'''
    for process in all_processes:
        if process != process_id:
            try:
                # O endpoint para receber mensagens de outros processos
                url = f"http://app-{process}.app-service:8000/recieve_message"
                url = f"http://app-{process}:8000/recieve_message"
                requests.post(url, json=message.model_dump(), timeout=0.5)
            except requests.RequestException as e:
                print(f"ERROR: Falha ao enviar mensagem para o processo {process}: {e}")


def broadcast_ack(original_message: Message):
    '''Envia ACK de uma mensagem a todos os outros processos'''
    ack_message = Ack(
        message_process_id=original_message.process_id,
        message_timestamp=original_message.timestamp,
        ack_source_process_id=process_id
    )
    for process in all_processes:
        if process != process_id:
            try:
                url = f"http://app-{process}.app-service:8000/recieve_ack"
                url = f"http://app-{process}:8000/recieve_ack"
                requests.post(url, json=ack_message.model_dump(), timeout=0.5)
            except requests.RequestException as e:
                print(f"ERROR: Falha ao enviar ACK para o processo {process}: {e}")

# --- Endpoints da API ---

@app.post('/recieve_external_message')
def recieve_external_message(message: str):
    '''Recebe uma mensagem de um cliente externo e inicia o multicast'''
    global internal_clock
    internal_clock += 1
    new_message = Message(data=message, process_id=process_id, timestamp=internal_clock)
    message_queue.append(new_message)
    broadcast_message(message_queue[-1])
    return 'ACK'


@app.post('/recieve_message')
def recieve_message(message: Message):
    '''Recebe uma mensagem de outro processo'''
    global internal_clock
    internal_clock = max(internal_clock, message.timestamp) + 1
    message_queue.append(message)
    # Envia ACK para todos os outros processos
    broadcast_ack(message)
    return 'ACK'
        

@app.post('/recieve_ack')
def recieve_ack(ack: Ack):
    '''Recebe um ACK de outro processo'''
    # Encontra a mensagem na fila que corresponde ao ACK
    for msg in message_queue:
        if msg.process_id == ack.message_process_id and msg.timestamp == ack.message_timestamp:
            if ack.ack_source_process_id not in msg.acks_sources:
                msg.acks_sources.append(ack.ack_source_process_id)
            break
    return 'ACK'

# --- Lógica de Entrega de Mensagens ---

def deliver_messages():
    '''Verifica a fila e entrega as mensagens que receberam todos os ACKs em ordem'''
    while True:
        message_queue.sort(key=lambda m: (m.timestamp, m.process_id))
        
        if message_queue and message_queue[0].verify_acks():
            delivered_message = message_queue.pop(0)
            print(f"DELIVERED: '{delivered_message.data}' from process {delivered_message.process_id} with timestamp {delivered_message.timestamp}")
        
        time.sleep(1)

if __name__ == "__main__":
    # Inicialização do processo
    internal_clock = 5 * process_id
    
    # Inicia a thread para entrega de mensagens
    delivery_thread = threading.Thread(target=deliver_messages, daemon=True)
    delivery_thread.start()
    
    print(f"Processo {process_id} iniciado.")
    uvicorn.run(app, host="0.0.0.0", port=8000)