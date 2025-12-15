# Exemplo de Exclusão Mútua com Algoritmo Token Ring

Este projeto demonstra uma implementação simples do algoritmo de exclusão mútua distribuída **Token Ring** usando Python, FastAPI, Docker e Kubernetes (Minikube).

O sistema consiste em 3 processos organizados em um anel lógico. Um "token" especial circula pelo anel, e apenas o processo que possui o token pode entrar na "seção crítica" (ou seja, acessar um recurso compartilhado).

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
    Isso permite que você construa imagens diretamente no registro do Minikube, evitando a necessidade de um registro de contêiner externo.
    ```sh
    # Para Linux/macOS
    eval $(minikube -p minikube docker-env)
    
    # Para PowerShell
    # & minikube -p minikube docker-env | Invoke-Expression
    ```

3.  **Construa a imagem Docker:**
    No diretório raiz do projeto, execute:
    ```sh
    docker build -t token-ring-app:latest .
    ```

4.  **Aplique o manifesto do Kubernetes:**
    Este comando criará os 3 Pods e os 3 Serviços necessários para o anel.
    ```sh
    kubectl apply -f minikube-deployment.yaml
    ```
    Aguarde até que todos os pods estejam no estado `Running`. Você pode verificar com `kubectl get pods -w`.

5.  **Execute o script de demonstração:**
    O script irá interagir com os processos para solicitar e liberar a seção crítica, mostrando o algoritmo em ação.
    ```sh
    chmod +x demo.sh
    ./demo.sh
    ```
    Enquanto o script é executado, você pode abrir outros terminais e acompanhar os logs de cada pod para ver a troca de mensagens em tempo real (ex: `kubectl logs -f <nome-do-pod-app-1>`).