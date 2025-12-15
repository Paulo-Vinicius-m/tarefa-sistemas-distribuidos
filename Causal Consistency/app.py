import sys
import time
import threading
import requests
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List, Dict
from collections import defaultdict

app = FastAPI()

# ------------------------------------------------------------
# Configuração
# ------------------------------------------------------------
processes = [
    "localhost:8080",
    "localhost:8081",
    "localhost:8082",
]

# ------------------------------------------------------------
# Estado global (instâncias e estruturas compartilhadas)
# ------------------------------------------------------------
myProcessId = 0          # id da réplica atual
data_lock = threading.Lock() 

# Relógio Vetorial: Uma posição para cada processo
vector_clock = [0] * len(processes)

# Buffer para mensagens que chegaram mas não satisfazem dependências causais
pending_buffer: List['Event'] = []

# Armazenamento de dados entregues
posts = defaultdict(list)
replies = defaultdict(list)

# ------------------------------------------------------------
# Modelo de evento
# ------------------------------------------------------------
class Event(BaseModel):
    processId: int
    evtId: str
    parentEvtId: Optional[str] = None
    author: str
    text: str
    # Agora usamos um Vetor de Inteiros em vez de um único int
    vector_clock: List[int] = [] 

# ------------------------------------------------------------
# Lógica de Consistência Causal
# ------------------------------------------------------------

def can_deliver(msg: Event) -> bool:
    """
    Verifica se a mensagem pode ser entregue garantindo Ordem Causal.
    Condições:
    1. Se for Reply, o Pai TEM que existir (regra da aplicação).
    2. Causal Broadcast: V_msg[sender] == V_local[sender] + 1
       (É a próxima mensagem sequencial deste remetente).
    3. Causal Broadcast: V_msg[k] <= V_local[k] para k != sender
       (Nós já sabemos tudo o que o remetente sabia sobre os outros processos).
    """
    sender_id = msg.processId

    # 1. Verificação de Dependência de Aplicação (Reply sem pai não entra)
    if msg.parentEvtId is not None:
        # Se o pai não está na lista de posts ENTREGUES, não podemos entregar o filho
        # (Lembrando que posts é defaultdict(list), checamos se a chave tem conteúdo)
        if msg.parentEvtId not in posts or not posts[msg.parentEvtId]:
            return False

    # 2. Verificação do Relógio Vetorial (Protocolo de Broadcast Causal)
    # A mensagem deve ser a próxima esperada do remetente
    if msg.vector_clock[sender_id] != vector_clock[sender_id] + 1:
        return False

    # Devemos ter visto todos os eventos causais que o remetente viu de OUTROS processos
    for k in range(len(processes)):
        if k != sender_id:
            if msg.vector_clock[k] > vector_clock[k]:
                return False

    return True

def try_deliver_pending():
    """
    Tenta entregar mensagens que estão no buffer.
    Sempre que uma mensagem é entregue, o estado muda, então reavaliamos o buffer.
    """
    changed = True
    while changed:
        changed = False
        # Itera sobre uma cópia para permitir remoção segura
        for msg in list(pending_buffer):
            if can_deliver(msg):
                # Entrega a mensagem
                processMsg(msg)
                
                # Atualiza nosso conhecimento sobre o remetente
                vector_clock[msg.processId] += 1
                
                # Remove do buffer
                pending_buffer.remove(msg)
                
                print(f"[Buffer] Mensagem {msg.evtId} desbloqueada e entregue.")
                
                # Reinicia o loop pois o vector_clock mudou, talvez libere outras
                changed = True 
                break 

# ------------------------------------------------------------
# Endpoints HTTP
# ------------------------------------------------------------

@app.post("/post")
def post(msg: Event):
    """
    Cria um novo post localmente.
    """
    with data_lock:
        # 1. Incrementa seu próprio relógio antes de criar evento
        vector_clock[myProcessId] += 1
        
        # 2. Anexa snapshot do relógio ao evento
        msg.vector_clock = vector_clock[:]
        msg.processId = myProcessId
        
        print(f"\n[Novo Evento Local] {msg.evtId} Clock: {msg.vector_clock}")

        # 3. Processa localmente (entrega imediata pois é local)
        processMsg(msg)
    
    # 4. Disseminar
    for idx, address in enumerate(processes):
        if idx != myProcessId:
            async_send(f"http://{address}/share", msg.dict())

    return {"status": "posted", "vector_clock": msg.vector_clock}


@app.post("/share")
def share(msg: Event):
    """
    Recebe evento de outra réplica.
    NÃO entrega imediatamente. Coloca no buffer e tenta entregar respeitando causalidade.
    """
    with data_lock:
        print(f"\n[Recebido] {msg.evtId} de P{msg.processId} Clock: {msg.vector_clock}")
        
        # Adiciona ao buffer primeiro
        pending_buffer.append(msg)
        
        # Tenta esvaziar o buffer se as dependências forem satisfeitas
        try_deliver_pending()

    # Atualiza a tela para mostrar estado (buffer ou feed)
    showFeed()
    return {"status": "received/buffered"}


# ------------------------------------------------------------
# Funções auxiliares
# ------------------------------------------------------------

def _send_thread(url: str, payload: dict):
    try:
        # Simula atraso no Nó 0 para forçar o cenário de buffer no Nó 1
        if myProcessId == 0: 
            time.sleep(3) 
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def async_send(url: str, payload: dict):
    t = threading.Thread(target=_send_thread, args=(url, payload))
    t.start()


def processMsg(msg: Event):
    """
    Efetiva a entrega da mensagem nas estruturas de dados visíveis (Feed).
    Neste ponto, a causalidade já está garantida.
    """
    if msg.parentEvtId is None:
        # Evita duplicatas simples
        current_list = posts[msg.evtId]
        if not any(p.evtId == msg.evtId for p in current_list):
            posts[msg.evtId].append(msg)
    else:
        current_replies = replies[msg.parentEvtId]
        if not any(r.evtId == msg.evtId for r in current_replies):
            replies[msg.parentEvtId].append(msg)
            # Ordena visualmente (opcional)
            replies[msg.parentEvtId].sort(key=lambda x: str(x.vector_clock))

    showFeed()


# ------------------------------------------------------------
# Apresentação
# ------------------------------------------------------------

def showFeed():
    """
    Exibe Feed (Entregues) e Buffer (Pendentes).
    """
    # Se não for chamado dentro de um lock existente, usaríamos lock aqui.
    # Como showFeed é chamado dentro das rotas com lock, ok. 
    # Mas por segurança em prints concorrentes:
    
    print("\n" + "="*60)
    print(f" NÓ {myProcessId} | V.Clock Local: {vector_clock}")
    print("="*60)
    
    # 1. Feed (Mensagens Causalmente Entregues)
    all_posts_flat = []
    for p_list in posts.values():
        all_posts_flat.extend(p_list)
    
    # Ordena posts apenas para visualização
    sorted_posts = sorted(all_posts_flat, key=lambda x: str(x.vector_clock))

    if not sorted_posts:
        print("(Feed Vazio)")

    for p in sorted_posts:
        print(f"POST [{p.evtId}] {p.vector_clock} {p.author}: {p.text}")
        p_replies = replies.get(p.evtId, [])
        for r in p_replies:
            print(f"   └── RE [{r.evtId}] {r.vector_clock} {r.author}: {r.text}")
        print("-" * 30)

    # 2. Buffer (Mensagens Retidas por falta de Causalidade)
    if pending_buffer:
        print(f"\n>>> BUFFER DE ESPERA (Violam Causalidade) - {len(pending_buffer)} msg(s) <<<")
        for m in pending_buffer:
            reason = "Aguardando ordem correta"
            if m.parentEvtId and (m.parentEvtId not in posts or not posts[m.parentEvtId]):
                reason = f"Post pai <{m.parentEvtId}> ausente"
            elif m.vector_clock[m.processId] != vector_clock[m.processId] + 1:
                 reason = f"Gap de sequência do remetente P{m.processId}"
            
            print(f" [BUFFERED] {m.evtId} (de P{m.processId}) ClockMsg: {m.vector_clock} -> Motivo: {reason}")
    else:
        print("\n(Buffer vazio - Sistema Sincronizado)")

    print("="*60 + "\n")


# ------------------------------------------------------------
# Inicialização
# ------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python eventual_consistency.py <processId [0,1,2]>")
        sys.exit(1)

    myProcessId = int(sys.argv[1])
    full_address = processes[myProcessId]
    host, port_str = full_address.split(":")
    
    print(f"Iniciando Causal Consistency Node {myProcessId}...")
    uvicorn.run(app, host=host, port=int(port_str), log_level="error")