#!/bin/bash

# Cores para o output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Sem Cor

echo -e "${YELLOW}=== INICIANDO DEMONSTRAÇÃO DO ALGORITMO BULLY ===${NC}"

# Pega o IP do Minikube
MINIKUBE_IP=$(minikube ip)
if [ -z "$MINIKUBE_IP" ]; then
    echo "Erro: não foi possível obter o IP do Minikube. Certifique-se de que ele está rodando."
    exit 1
fi

URL_P1="http://$MINIKUBE_IP:30011"
URL_P2="http://$MINIKUBE_IP:30012"
URL_P3="http://$MINIKUBE_IP:30013"

echo "IP do Minikube: $MINIKUBE_IP"
echo "Processo 1 acessível em: $URL_P1"
echo "Processo 2 acessível em: $URL_P2"
echo "Processo 3 acessível em: $URL_P3"

# Função para checar o status de todos os pods
check_status() {
    echo -e "\n${GREEN}Status atual dos processos:${NC}"
    echo -n "  P1: "; curl -s "$URL_P1/status" || echo -e "${RED}OFFLINE${NC}"
    echo ""
    echo -n "  P2: "; curl -s "$URL_P2/status" || echo -e "${RED}OFFLINE${NC}"
    echo ""
    echo -n "  P3: "; curl -s "$URL_P3/status" || echo -e "${RED}OFFLINE${NC}"
    echo ""
}

echo -e "\n${YELLOW}Passo 1: Inicialização do cluster.${NC}"
echo "O processo 3 (maior ID) deve se tornar o líder inicial."
echo "Observe os logs dos pods com 'kubectl logs -f <nome-do-pod>'"

check_status

echo -e "\n${YELLOW}Passo 2: Simulando uma falha no líder (Processo 3)...${NC}"
echo "Vamos escalar o deployment do app-3 para 0 réplicas."
kubectl scale deployment bully-app-3-deployment --replicas=0
sleep 5 # Dar tempo para o pod ser terminado

check_status

echo -e "\n${YELLOW}Passo 3: Aguardando a detecção da falha e uma nova eleição... (15s)${NC}"
echo "Os processos 1 e 2 tentarão contatar o líder 3. Ao falharem, iniciarão uma eleição."
echo "O processo 2 deve vencer e se tornar o novo líder."
sleep 15

check_status

echo -e "\n${YELLOW}Passo 4: Simulando a recuperação do Processo 3...${NC}"
echo "Vamos escalar o deployment do app-3 de volta para 1 réplica."
kubectl scale deployment bully-app-3-deployment --replicas=1
echo "Aguardando o pod do Processo 3 iniciar... (20s)"
sleep 20

check_status
echo "O líder atual ainda é o Processo 2, pois nenhuma eleição foi iniciada."

echo -e "\n${YELLOW}Passo 5: Iniciando uma eleição manualmente a partir do Processo 1...${NC}"
echo "O Processo 1 vai notar que o Processo 3 (maior ID) está de volta e vai ceder a liderança."
curl -s -X POST "$URL_P1/trigger_election"
echo -e "\nEleição iniciada. Aguardando o resultado... (10s)"
sleep 10

check_status
echo "O Processo 3 deve ser o novo líder."

echo -e "\n${YELLOW}=== DEMONSTRAÇÃO CONCLUÍDA ===${NC}"
echo "Restaurando o estado do deployment do app-3 para 1 (caso o script seja interrompido)."
kubectl scale deployment bully-app-3-deployment --replicas=1