# Exemplo de Eleição de Líder com Algoritmo do Valentão (Bully)

Este projeto demonstra uma implementação simples do algoritmo de eleição de líder **Bully** em um sistema distribuído, usando Python, FastAPI, Docker e Kubernetes (Minikube).

O sistema consiste em 3 processos. Quando o líder atual falha, ou quando um processo percebe que não há um líder, uma eleição é iniciada. No algoritmo do Valentão, o processo com o maior ID que está ativo sempre se torna o líder.

## Tecnologias Utilizadas

- **Python 3.10+**
- **FastAPI**: Para criar a API web em cada processo.
- **Docker**: Para containerizar a aplicação.
- **Kubernetes (Minikube)**: Para orquestrar os contêineres e simular um ambiente distribuído.

## Como Executar

### Pré-requisitos

- [Docker](https://www.docker.com/get-started) instalado.
- [Minikube](https://minikube.sigs.k8s.io/docs/start/) instalado.

### Passos

1.  **Inicie o Minikube:**
    ```sh
    minikube start
    ```

2.  **Aponte seu terminal para o ambiente Docker do Minikube:**
    Isso permite que você construa imagens diretamente no registro do Minikube.
    ```sh
    # Para Linux/macOS
    eval $(minikube -p minikube docker-env)
    
    # Para PowerShell
    # & minikube -p minikube docker-env | Invoke-Expression
    ```

3.  **Construa a imagem Docker:**
    No diretório do projeto, execute:
    ```sh
    docker build -t bully-app:latest .
    ```

4.  **Aplique o manifesto do Kubernetes:**
    ```sh
    kubectl apply -f minikube-deployment.yaml
    ```
    Aguarde até que todos os pods estejam no estado `Running` (`kubectl get pods -w`). O processo de maior ID (3) deve se anunciar como líder inicial.

5.  **Execute o script de demonstração:**
    O script irá simular a falha do líder, observar a nova eleição e, em seguida, reintroduzir o processo antigo para mostrar como ele retoma a liderança.
    ```sh
    chmod +x demo.sh
    ./demo.sh
    ```
    Enquanto o script é executado, você pode abrir outros terminais e acompanhar os logs de cada pod para ver as mensagens de eleição em tempo real (ex: `kubectl logs -f <nome-do-pod-bully-app-1>`).