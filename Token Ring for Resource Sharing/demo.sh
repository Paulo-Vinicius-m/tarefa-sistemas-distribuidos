#!/bin/bash

# Cores para o output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # Sem Cor

echo -e "${YELLOW}=== INICIANDO DEMONSTRAÇÃO DO TOKEN RING ===${NC}"

# Pega o IP do Minikube
MINIKUBE_IP=$(minikube ip)
if [ -z "$MINIKUBE_IP" ]; then
    echo "Erro: não foi possível obter o IP do Minikube. Certifique-se de que ele está rodando."
    exit 1
fi

URL_P1="http://$MINIKUBE_IP:30001"
URL_P2="http://$MINIKUBE_IP:30002"
URL_P3="http://$MINIKUBE_IP:30003"

echo "IP do Minikube: $MINIKUBE_IP"
echo "Processo 1 acessível em: $URL_P1"
echo "Processo 2 acessível em: $URL_P2"
echo "Processo 3 acessível em: $URL_P3"

echo -e "\n${GREEN}Status atual:${NC}"
curl -s "$URL_P1/status" | sed 's/^/  P1: /'
echo ""
curl -s "$URL_P2/status" | sed 's/^/  P2: /'
echo ""
curl -s "$URL_P3/status" | sed 's/^/  P3: /'

echo -e "\n${YELLOW}Passo 2: Processo 2 solicita acesso à Seção Crítica (SC)...${NC}"
curl -s -X POST "$URL_P2/request_cs"
echo -e "\nO Processo 2 agora está com 'wants_to_enter_cs: true' e vai esperar o token."

echo -e "\n${GREEN}Status atual:${NC}"
curl -s "$URL_P1/status" | sed 's/^/  P1: /'
echo ""
curl -s "$URL_P2/status" | sed 's/^/  P2: /'
echo ""
curl -s "$URL_P3/status" | sed 's/^/  P3: /'

echo -e "\n${YELLOW}Passo 3: Aguardando o Processo 2 receber o token e entrar na SC... (3s)${NC}"
sleep 3
echo -e "O token deve parar de circular agora."

echo -e "\n${GREEN}Status atual (P2 deve estar na SC):${NC}"
curl -s "$URL_P1/status" | sed 's/^/  P1: /'
echo ""
curl -s "$URL_P2/status" | sed 's/^/  P2: /'
echo ""
curl -s "$URL_P3/status" | sed 's/^/  P3: /'

echo -e "\n${YELLOW}Passo 4: Processo 2 libera a Seção Crítica...${NC}"
curl -s -X POST "$URL_P2/release_cs"
echo -e "\nO Processo 2 liberou a SC e passou o token adiante. A circulação recomeça."

echo -e "\n${YELLOW}Passo 5: Aguardando o token circular novamente... (1s)${NC}"
sleep 1

echo -e "\n${GREEN}Status final (token deve estar com P3 ou P1):${NC}"
curl -s "$URL_P1/status" | sed 's/^/  P1: /'
echo ""
curl -s "$URL_P2/status" | sed 's/^/  P2: /'
echo ""
curl -s "$URL_P3/status" | sed 's/^/  P3: /'

echo -e "\n${YELLOW}=== DEMONSTRAÇÃO CONCLUÍDA ===${NC}"