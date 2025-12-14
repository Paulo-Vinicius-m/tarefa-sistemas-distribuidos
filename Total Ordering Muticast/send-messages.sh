#!/bin/bash

# Usaremos kubectl port-forward para uma conexão mais estável em scripts.
# Ele encaminha uma porta local para a porta de um serviço.

LOCAL_PORT_1=8081
LOCAL_PORT_3=8083

echo "--- Criando túnel para o serviço app-1 na porta local ${LOCAL_PORT_1} ---"
kubectl port-forward service/app-1 ${LOCAL_PORT_1}:8000 &
PF_PID_1=$!

echo "--- Criando túnel para o serviço app-3 na porta local ${LOCAL_PORT_3} ---"
kubectl port-forward service/app-3 ${LOCAL_PORT_3}:8000 &
PF_PID_3=$!

# Aguarda um momento para os túneis serem estabelecidos
sleep 3

echo
echo "Enviando 'Primeira mensagem' para o processo 1 (via localhost:${LOCAL_PORT_1})..."
curl -X POST "http://localhost:${LOCAL_PORT_1}/recieve_external_message?message=Primeira%20mensagem"

echo
echo "Enviando 'Segunda mensagem' para o processo 3 (via localhost:${LOCAL_PORT_3})..."
curl -X POST "http://localhost:${LOCAL_PORT_3}/recieve_external_message?message=Segunda%20mensagem"

echo
echo "Enviando 'Terceira mensagem' para o processo 3 (via localhost:${LOCAL_PORT_3})..."
curl -X POST "http://localhost:${LOCAL_PORT_3}/recieve_external_message?message=Terceira%20mensagem"

echo
echo "Enviando 'Quarta mensagem' para o processo 1 (via localhost:${LOCAL_PORT_1})..."
curl -X POST "http://localhost:${LOCAL_PORT_1}/recieve_external_message?message=Quarta%20mensagem"

echo -e "\n\n--- Mensagens enviadas. Observe os logs dos pods com 'kubectl logs -f <nome-do-pod>' ---"

# Limpeza: encerra os processos de port-forward
echo "--- Encerrando os túneis de port-forward ---"
kill $PF_PID_1
kill $PF_PID_3

wait $PF_PID_1 2>/dev/null
wait $PF_PID_3 2>/dev/null