# Demonstração de Multicast com Ordenação Total usando Minikube

Este projeto implementa e ilustra o funcionamento de um algoritmo de multicast com ordenação total, baseado no algoritmo de Lamport.

Três instâncias de uma aplicação Python (usando FastAPI) são executadas em um cluster Minikube. Elas se comunicam para garantir que todas as mensagens recebidas sejam entregues (processadas) na mesma ordem em todas as instâncias, independentemente da ordem de chegada.

## Pré-requisitos

*   [Minikube](https://minikube.sigs.k8s.io/docs/start/)
*   [Docker](https://docs.docker.com/get-docker/)
*   [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)

## Como Executar

Siga os passos abaixo para configurar e testar a aplicação.

### 1. Inicie o Minikube

```bash
minikube start
```

### 2. Construa a Imagem Docker

Para que o Minikube possa usar a imagem Docker local, precisamos construí-la dentro do ambiente do próprio Minikube.

```bash
# Aponta seu terminal para o daemon Docker do Minikube
eval $(minikube -p minikube docker-env)

# Constrói a imagem
docker build -t total-ordering-app:latest .
```

### 3. Inicie as Aplicações no Kubernetes

Aplique o arquivo de configuração para criar os Deployments e Services no cluster.

```bash
kubectl apply -f minikube-config.yaml
```

Você pode verificar se os 3 pods estão rodando com `kubectl get pods`.

### 4. Observe os Logs

Para ver o algoritmo em ação, abra **3 terminais diferentes**. Em cada um, acompanhe o log de um dos pods.

Primeiro, liste os pods para obter seus nomes: `kubectl get pods`. Depois, em cada terminal, execute (substituindo `<nome-do-pod>`):

```bash
# Terminal 1: kubectl logs -f <nome-do-pod-app-1>
# Terminal 2: kubectl logs -f <nome-do-pod-app-2>
# Terminal 3: kubectl logs -f <nome-do-pod-app-3>
```

### 5. Envie Mensagens para Teste

Em um **quarto terminal**, execute o script `send-messages.sh` para enviar duas mensagens para instâncias diferentes.

```bash
chmod +x send-messages.sh
./send-messages.sh
```

### O que Observar

Nos logs dos três terminais, você verá as mensagens sendo recebidas, os ACKs sendo trocados e, finalmente, as mensagens sendo entregues com a tag `DELIVERED: ...`.

O ponto principal da demonstração é que a **ordem de entrega (`DELIVERED`) será a mesma em todos os três pods**, provando o funcionamento do algoritmo de ordenação total.

### 6. Limpeza

Quando terminar, remova todos os recursos do Kubernetes criados:

```bash
kubectl delete -f minikube-config.yaml
```