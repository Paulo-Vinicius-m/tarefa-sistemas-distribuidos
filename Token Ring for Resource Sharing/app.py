import fastapi
import requests
import os
import uvicorn
import threading
import time

app = fastapi.FastAPI()

process_id = int(os.getenv("PROCESS_ID", "1"))
all_processes = [1, 2, 3]
next_process_id = (process_id % len(all_processes)) + 1

# --- Estado Protegido ---
# Lock para proteger TODAS as variáveis de estado
state_lock = threading.Lock()

has_token = False
wants_to_enter_cs = False
in_critical_section = False

def pass_token():
    global has_token
    
    # O Lock deve ser adquirido ANTES de ler ou escrever o estado
    # No entanto, pass_token geralmente é chamado de dentro de funções 
    # que já seguram o lock (recursividade). 
    # Para simplificar, vamos assumir que quem chama pass_token já tem o lock
    # ou vamos checar o estado cuidadosamente.
    
    # OBS: requests.post é I/O bloqueante e lento. 
    # NÃO devemos segurar o lock durante a requisição de rede se possível,
    # mas devemos segurar enquanto modificamos has_token.
    
    should_send = False
    
    with state_lock:
        if has_token:
            has_token = False
            should_send = True
    
    if should_send:
        print(f"Processo {process_id} passando o token...")
        try:
            url = f"http://app-{next_process_id}:8000/receive_token"
            requests.post(url, timeout=10)
        except Exception as e:
            print(f"Erro ao passar token: {e}")

def process_received_token():
    global in_critical_section, wants_to_enter_cs
    
    with state_lock:
        if wants_to_enter_cs:
            in_critical_section = True
            wants_to_enter_cs = False
            print(f"Processo {process_id} ENTROU na SC.")
            should_pass = False
        else:
            print(f"Processo {process_id} passando token adiante.")
            should_pass = True

    # Realiza a ação fora do bloco do lock principal se envolver I/O pesado ou sleep
    if should_pass:
        time.sleep(1) 
        pass_token()

@app.post("/request_cs")
def request_cs():
    global wants_to_enter_cs
    with state_lock:
        if in_critical_section:
            return {"status": "Erro", "message": "Já na SC."}
        if wants_to_enter_cs:
            return {"status": "OK", "message": "Já aguardando."}
        
        print(f"Processo {process_id} deseja entrar na SC.")
        wants_to_enter_cs = True
    return {"status": "OK"}

@app.post("/release_cs")
def release_cs():
    global in_critical_section
    
    should_pass = False
    with state_lock:
        if not in_critical_section:
            return {"status": "Erro", "message": "Não está na SC."}
        
        print(f"Processo {process_id} saindo da SC.")
        in_critical_section = False
        should_pass = True
    
    if should_pass:
        pass_token()
        
    return {"status": "OK"}

@app.post("/receive_token")
def receive_token():
    global has_token
    
    process_it = False
    with state_lock:
        if has_token:
            return {"status": "Ignorado"}
        print(f"Processo {process_id} RECEBEU o token.")
        has_token = True
        process_it = True
    
    if process_it:
        process_received_token()
        
    return {"status": "ACK"}

@app.get("/status")
def get_status():
    """Retorna o estado atual do processo para fins de depuração."""
    return {
        "process_id": process_id,
        "has_token": has_token,
        "wants_to_enter_cs": wants_to_enter_cs,
        "in_critical_section": in_critical_section,
    }

# --- Inicialização do Processo ---

def initial_token_holder():
    """
    Função executada em uma thread separada pelo processo 1 para iniciar a circulação do token.
    Espera um tempo para garantir que os outros processos estejam online.
    """
    # Espera para dar tempo aos outros contêineres/processos de iniciarem
    startup_delay = 5
    print(f"Processo 1 (inicializador) aguardando {startup_delay}s antes de iniciar o anel...")
    time.sleep(startup_delay)
    
    global has_token
    print("Processo 1 assume a posse inicial do token.")
    has_token = True
    process_received_token()

if __name__ == "__main__":
    # Apenas o processo com ID 1 começa com o token.
    if process_id == 1:
        # Inicia uma thread para dar o pontapé inicial na circulação do token.
        # Usar uma thread evita bloquear a inicialização do servidor uvicorn.
        initialization_thread = threading.Thread(target=initial_token_holder, daemon=True)
        initialization_thread.start()

    print(f"Processo {process_id} iniciado. Próximo no anel: {next_process_id}.")
    uvicorn.run(app, host="0.0.0.0", port=8000)