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
# Estado global (instâncias e estruturas compartilhadas)
# ------------------------------------------------------------
myProcessId = 0          # id da réplica atual (definido via argv na inicialização)
timestamp = 0            # relógio lógico (Lamport) local
data_lock = threading.Lock() # Lock para proteger acesso concorrente às estruturas

# Revertido para defaultdict(list) conforme solicitado
# Estrutura: {evtId: [Event, ...]}
posts = defaultdict(list)
# Replies agrupados pelo ID do pai: {parentEvtId: [Event, Event]}
replies = defaultdict(list)

processes = [
    "localhost:8080",
    "localhost:8081",
    "localhost:8082",
]

# ------------------------------------------------------------
# Modelo de evento
# ------------------------------------------------------------
class Event(BaseModel):
    processId: int
    evtId: str
    parentEvtId: Optional[str] = None
    author: str
    text: str
    timestamp: Optional[int] = None # Relógio lógico do evento

# ------------------------------------------------------------
# Endpoints HTTP
# ------------------------------------------------------------

@app.post("/post")
def post(msg: Event):
    """
    Endpoint usado para criar um novo post localmente.
    """
    global timestamp
    
    # 1. Atualizar relógio lógico
    with data_lock:
        timestamp += 1
        msg.timestamp = timestamp
        # Sobrescreve o ID para garantir que é do nó atual se criado aqui
        msg.processId = myProcessId 

    print(f"\n[Novo Evento Local] {msg.evtId} por {msg.author}")

    # 2. Processar localmente
    processMsg(msg)

    # 3. Disseminar para as outras réplicas (Gossip/Broadcast)
    for idx, address in enumerate(processes):
        if idx != myProcessId:
            # Envia para a rota /share dos vizinhos
            target_url = f"http://{address}/share"
            async_send(target_url, msg.dict())

    return {"status": "posted", "timestamp": msg.timestamp}


@app.post("/share")
def share(msg: Event):
    """
    Endpoint usado para receber eventos enviados por outras réplicas.
    """
    global timestamp

    # 1. Atualizar relógio lógico local (Lamport: max(local, received) + 1)
    with data_lock:
        if msg.timestamp and msg.timestamp > timestamp:
            timestamp = msg.timestamp
        timestamp += 1 # Incremento pelo evento de recebimento

    print(f"\n[Recebido via Gossip] {msg.evtId} vindo do Proc {msg.processId}")

    # 2. Processar msg
    processMsg(msg)

    return {"status": "received"}


# ------------------------------------------------------------
# Funções auxiliares de rede e aplicação
# ------------------------------------------------------------

def _send_thread(url: str, payload: dict):
    """Função interna executada pela thread."""
    try:
        # Simula atraso de rede aleatório para evidenciar a consistência eventual
        if myProcessId == 0: 
            time.sleep(2) # Nó 0 é artificialmente lento para enviar
        
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f" [!] Falha ao enviar para {url}: {e}")

def async_send(url: str, payload: dict):
    """
    Envia um payload JSON para outra réplica de forma assíncrona.
    """
    t = threading.Thread(target=_send_thread, args=(url, payload))
    t.start()


def processMsg(msg: Event):
    """
    Aplica um evento ao estado local (feed).
    Consistência Eventual: Aceita replies mesmo se o pai não existe.
    """
    with data_lock:
        # Verifica se já processamos esse evento (idempotência básica)
        if msg.parentEvtId is None:
            # Lógica para defaultdict(list): verifica se msg já está na lista desse ID
            current_list = posts[msg.evtId]
            if any(p.evtId == msg.evtId and p.processId == msg.processId for p in current_list):
                return # Já temos
            posts[msg.evtId].append(msg)
        else:
            # Verifica duplicação na lista de replies
            current_replies = replies[msg.parentEvtId]
            if any(r.evtId == msg.evtId for r in current_replies):
                return # Já temos
            replies[msg.parentEvtId].append(msg)
            # Ordena replies por timestamp para exibição consistente
            replies[msg.parentEvtId].sort(key=lambda x: x.timestamp or 0)

    # Atualiza a tela
    showFeed()


# ------------------------------------------------------------
# Apresentação / debug
# ------------------------------------------------------------

def showFeed():
    """
    Exibe no console o estado atual do feed local.
    """
    print("\n" + "="*50)
    print(f" FEED DO PROCESSO {myProcessId} | Clock Atual: {timestamp}")
    print("="*50)
    
    with data_lock:
        # 1. Exibir Posts conhecidos
        # Precisamos "achatar" a lista de posts, já que agora posts é um dict de listas
        all_posts_flat = []
        for p_list in posts.values():
            all_posts_flat.extend(p_list)
            
        sorted_posts = sorted(all_posts_flat, key=lambda x: x.timestamp or 0)

        if not sorted_posts and not replies:
            print("(Feed vazio)")

        for p in sorted_posts:
            print(f"POST [{p.evtId}] (T={p.timestamp}) {p.author}: {p.text}")
            
            # Exibir replies deste post
            p_replies = replies.get(p.evtId, [])
            for r in p_replies:
                print(f"   └── RE [{r.evtId}] (T={r.timestamp}) {r.author}: {r.text}")
            
            print("-" * 20)

        # 2. Exibir Replies Órfãos (Consistência Eventual em ação)
        # Replies cujo parentEvtId não está no dicionário posts (ou a lista está vazia)
        all_parents_with_replies = set(replies.keys())
        
        # Filtra apenas IDs que possuem posts reais carregados
        known_posts_ids = {pid for pid, plist in posts.items() if plist}
        
        orphan_parents = all_parents_with_replies - known_posts_ids

        if orphan_parents:
            print("\n>>> REPLIES ÓRFÃOS (Post pai ainda não chegou) <<<")
            for parent_id in orphan_parents:
                print(f"Ref: Pai desconhecido <{parent_id}>")
                for r in replies[parent_id]:
                    print(f"   └── RE [{r.evtId}] (T={r.timestamp}) {r.author}: {r.text}")

    print("="*50 + "\n")


# ------------------------------------------------------------
# Inicialização do nó
# ------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python eventual.py <processId [0,1,2]>")
        sys.exit(1)

    myProcessId = int(sys.argv[1])
    
    # Extrai host e porta da lista de processos
    full_address = processes[myProcessId]
    host, port_str = full_address.split(":")
    port = int(port_str)

    print(f"Iniciando Processo {myProcessId} em {host}:{port}...")
    
    # Executa o servidor
    uvicorn.run(app, host=host, port=port, log_level="error")