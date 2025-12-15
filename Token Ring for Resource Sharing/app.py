import fastapi
import requests
import os
import uvicorn
import threading
import time

app = fastapi.FastAPI()

# --- Variáveis Globais ---
# Identificador do processo, obtido da variável de ambiente PROCESS_ID. Padrão é 1.
process_id = int(os.getenv("PROCESS_ID", "1"))
# Lista de todos os processos no anel.
all_processes = [1, 2, 3]
# Identificador do próximo processo no anel lógico.
next_process_id = (process_id % len(all_processes)) + 1

# --- Estado do Algoritmo Token Ring ---
has_token = False
wants_to_enter_cs = False
in_critical_section = False

# --- Funções do Algoritmo ---

def pass_token():
    """
    Passa o token para o próximo processo no anel.
    Esta função é chamada quando o processo atual libera a seção crítica
    ou quando recebe o token, mas não precisa dele.
    """
    global has_token
    if not has_token:
        # Isso não deveria acontecer, mas é uma boa verificação de sanidade.
        print(f"AVISO: Processo {process_id} tentou passar o token, mas não o possui.")
        return

    has_token = False
    print(f"Processo {process_id} passando o token para o processo {next_process_id}.")
    
    # Tenta enviar o token para o próximo processo
    try:
        url = f"http://app-{next_process_id}:8000/receive_token"
        # O timeout é curto porque a rede interna (ex: Docker) deve ser rápida.
        requests.post(url, timeout=1)
    except requests.RequestException as e:
        print(f"ERRO: Falha ao enviar token para o processo {next_process_id}: {e}")
        # Em um sistema real, seria necessário um tratamento de falhas mais robusto,
        # como reconstruir o anel. Para este exemplo, o token é "perdido" se o
        # próximo processo estiver offline.
        print(f"AVISO: Token não pode ser passado. O anel pode estar quebrado.")


def process_received_token():
    """
    Decide o que fazer com o token recém-recebido.
    Se o processo quer entrar na seção crítica, ele o faz.
    Caso contrário, passa o token adiante.
    """
    global in_critical_section, wants_to_enter_cs
    
    if wants_to_enter_cs:
        # O processo quer usar o recurso, então entra na seção crítica
        in_critical_section = True
        wants_to_enter_cs = False
        print(f"Processo {process_id} ENTROU na Seção Crítica (SC).")
        # O processo manterá o token até que a SC seja liberada
    else:
        # O processo não precisa da SC, então passa o token imediatamente
        print(f"Processo {process_id} não precisa da SC, passando o token adiante.")
        # Adiciona um pequeno delay para facilitar a visualização do fluxo
        time.sleep(1)
        pass_token()


# --- Endpoints da API ---

@app.post("/request_cs")
def request_cs():
    """
    Endpoint para um cliente externo solicitar acesso à Seção Crítica (SC).
    """
    global wants_to_enter_cs
    if in_critical_section:
        return {"status": "Erro", "message": f"Processo {process_id} já está na Seção Crítica."}
    if wants_to_enter_cs:
        return {"status": "OK", "message": f"Processo {process_id} já está aguardando para entrar na SC."}
    
    print(f"Processo {process_id} recebeu uma requisição e agora DESEJA entrar na SC.")
    wants_to_enter_cs = True
    return {"status": "OK", "message": f"Requisição registrada. Processo {process_id} aguardará pelo token."}

@app.post("/release_cs")
def release_cs():
    """
    Endpoint para um cliente externo sinalizar que o processo pode sair da Seção Crítica.
    """
    global in_critical_section
    if not in_critical_section:
        return {"status": "Erro", "message": f"Processo {process_id} não está na Seção Crítica."}

    print(f"Processo {process_id} recebeu uma requisição para SAIR da SC.")
    in_critical_section = False
    pass_token()
    return {"status": "OK", "message": "Seção Crítica liberada e token passado adiante."}

@app.post("/receive_token")
def receive_token():
    """
    Recebe o token do processo anterior no anel.
    """
    global has_token
    if has_token:
        # Isso pode acontecer em cenários de falha de rede e retransmissão.
        print(f"AVISO: Processo {process_id} recebeu o token, mas já o possuía. Ignorando.")
        return {"status": "Ignorado"}

    print(f"Processo {process_id} RECEBEU o token.")
    has_token = True
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