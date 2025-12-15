import fastapi
import requests
import os
import uvicorn
import threading
import time
from typing import List, Optional

app = fastapi.FastAPI()

# --- Estado Global ---
process_id = int(os.getenv("PROCESS_ID", "0"))
all_processes = [1, 2, 3] # IDs de todos os processos no sistema
leader_id: Optional[int] = None
is_election_happening = False
# Um lock para evitar condições de corrida ao modificar estados compartilhados
state_lock = threading.Lock()

# --- Funções Auxiliares do Algoritmo ---

def get_higher_processes() -> List[int]:
    """Retorna uma lista de IDs de processos maiores que o atual."""
    return [p for p in all_processes if p > process_id]

def announce_leader():
    """Anuncia para todos os outros processos que este se tornou o líder."""
    global leader_id, is_election_happening
    with state_lock:
        print(f"Processo {process_id} se autoproclamando LÍDER.")
        leader_id = process_id
        is_election_happening = False

    # Envia mensagem de coordenação para todos os outros processos
    for p_id in all_processes:
        if p_id != process_id:
            try:
                url = f"http://app-{p_id}:8000/coordinator"
                requests.post(url, json={"leader_id": process_id}, timeout=0.5)
                print(f"Processo {process_id} anunciou liderança para {p_id}.")
            except requests.RequestException:
                print(f"AVISO: Falha ao anunciar liderança para o processo {p_id}.")

def start_election():
    """Inicia um processo de eleição."""
    global is_election_happening
    
    with state_lock:
        if is_election_happening:
            print(f"Processo {process_id} já está em uma eleição. Ignorando nova tentativa.")
            return
        print(f"Processo {process_id} INICIOU UMA ELEIÇÃO.")
        is_election_happening = True

    higher_processes = get_higher_processes()
    if not higher_processes:
        # Se não há processos com ID maior, este se torna o líder.
        announce_leader()
        return

    # Envia mensagem de eleição para todos os processos com ID maior
    responses_from_higher = 0
    for p_id in higher_processes:
        try:
            url = f"http://app-{p_id}:8000/election"
            requests.post(url, json={"sender_id": process_id}, timeout=1)
            # Se a requisição foi bem-sucedida, significa que um processo maior está ativo.
            responses_from_higher += 1
            print(f"Processo {process_id} enviou msg de eleição para {p_id} e recebeu resposta.")
        except requests.RequestException:
            # O processo com ID maior provavelmente está inativo.
            print(f"Processo {process_id} não obteve resposta de eleição do processo {p_id}.")

    # Se nenhum processo superior respondeu, este processo se torna o líder.
    if responses_from_higher == 0:
        announce_leader()
    else:
        # Um processo superior assumiu. Apenas aguarda o anúncio do novo líder.
        print(f"Processo {process_id} aguardando anúncio do novo líder...")

# --- Endpoints da API ---

@app.post("/election")
def handle_election_message(data: dict):
    """Recebe uma mensagem de eleição de um processo com ID menor."""
    sender_id = data.get("sender_id")
    print(f"Processo {process_id} recebeu mensagem de eleição de {sender_id}.")
    
    # Responde ao remetente (a própria resposta HTTP 200 OK serve como "resposta")
    # e inicia sua própria eleição, pois tem um ID maior.
    threading.Thread(target=start_election).start()
    
    return {"status": "OK, I will take over."}

@app.post("/coordinator")
def handle_coordinator_message(data: dict):
    """Recebe uma mensagem anunciando o novo líder."""
    global leader_id, is_election_happening
    new_leader_id = data.get("leader_id")
    
    with state_lock:
        if leader_id != new_leader_id:
            print(f"Processo {process_id} reconheceu o novo líder: {new_leader_id}.")
            leader_id = new_leader_id
        is_election_happening = False
        
    return {"status": "ACK"}

@app.post("/trigger_election")
def trigger_election_endpoint():
    """Endpoint externo para iniciar uma eleição manualmente."""
    print(f"Processo {process_id} recebeu um gatilho externo para iniciar a eleição.")
    threading.Thread(target=start_election).start()
    return {"message": "Processo de eleição iniciado."}

@app.get("/status")
def get_status():
    """Retorna o status atual do processo."""
    return {
        "process_id": process_id,
        "leader_id": leader_id,
        "is_election_happening": is_election_happening,
    }

@app.get("/healthcheck")
def healthcheck():
    """Endpoint simples para verificar se o processo está ativo."""
    return {"status": "alive"}

# --- Tarefa em Background para Detecção de Falhas ---

def check_leader_health():
    """Verifica periodicamente se o líder está ativo. Se não, inicia uma eleição."""
    while True:
        time.sleep(10) # Verifica a cada 10 segundos
        
        with state_lock:
            # Não faz nada se uma eleição já está ocorrendo ou se este processo é o líder
            if is_election_happening or leader_id == process_id:
                continue
            
            # Se não há líder, inicia uma eleição
            if leader_id is None:
                print(f"Processo {process_id}: Nenhum líder conhecido. Iniciando eleição.")
                start_election()
                continue

        # Se há um líder, verifica sua saúde
        try:
            url = f"http://app-{leader_id}:8000/healthcheck"
            requests.get(url, timeout=2)
        except requests.RequestException:
            print(f"Processo {process_id}: Falha ao contatar o líder {leader_id}. Iniciando eleição.")
            start_election()

if __name__ == "__main__":
    # Aguarda um tempo para que todos os pods iniciem antes de começar as verificações
    print(f"Processo {process_id} iniciado. Aguardando 15s para estabilização do cluster...")
    time.sleep(15)
    
    # Inicia a thread em background para verificar a saúde do líder
    health_check_thread = threading.Thread(target=check_leader_health, daemon=True)
    health_check_thread.start()

    # O processo com maior ID se declara líder inicialmente para começar o sistema
    if process_id == max(all_processes):
        print(f"Processo {process_id} é o de maior ID, assumindo liderança inicial.")
        time.sleep(2) # Pequeno delay para garantir que os outros processos estejam escutando
        announce_leader()
    
    print(f"Servidor do processo {process_id} rodando.")
    uvicorn.run(app, host="0.0.0.0", port=8000)