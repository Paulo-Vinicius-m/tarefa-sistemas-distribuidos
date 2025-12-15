#!/bin/bash

# ==============================================================================
# Script de Demonstração: Consistência Eventual
# ==============================================================================
# Este script levanta 3 instâncias do sistema distribuído e simula:
# 1. Criação de um post no Nó 0.
# 2. Criação imediata de uma resposta (reply) no Nó 1.
# 3. Devido ao atraso simulado no código Python (Nó 0 demora a enviar),
#    o Nó 1 receberá o reply ANTES do post original, gerando um "Reply Órfão".
# 4. Após alguns segundos, o post original chega e a consistência é atingida.
# ==============================================================================

# Função para limpar processos ao encerrar o script (Ctrl+C ou fim da execução)
cleanup() {
    echo ""
    echo "🛑 Encerrando todos os nós..."
    # Mata os jobs em background iniciados por este script
    kill $(jobs -p) 2>/dev/null
    wait
    echo "✅ Demo finalizada."
}

# Configura a trap para pegar o sinal de saída
trap cleanup SIGINT EXIT

echo "🚀 Iniciando Cluster..."

# Inicia os 3 nós em background
# (O output deles aparecerá misturado neste terminal, permitindo ver os logs 'showFeed')
python app.py 0 &
PID0=$!
echo "   -> Nó 0 iniciado (PID $PID0) em :8080"

python app.py 1 &
PID1=$!
echo "   -> Nó 1 iniciado (PID $PID1) em :8081"

python app.py 2 &
PID2=$!
echo "   -> Nó 2 iniciado (PID $PID2) em :8082"

# Aguarda inicialização do Uvicorn
echo "⏳ Aguardando startup (5s)..."
sleep 5
echo ""
echo "============================================================"
echo "Cluster Operacional. Iniciando cenário de teste."
echo "============================================================"
echo ""

# 1. Post Normal no Nó 0
# O código Python força um sleep(2) no envio do Nó 0, então ele vai reter a msg um pouco.
echo "🔵 [1/3] Enviando POST 'evt_A' para o Nó 0 (Alice)..."
curl -s -X POST http://localhost:8080/post \
-H "Content-Type: application/json" \
-d '{"processId": 0, "evtId": "evt_A", "author": "Alice", "text": "Ola Distribuido!"}'
echo ""
echo ""

# 2. Reply Imediato no Nó 1
# Como o Nó 0 está "dormindo" antes de enviar o 'evt_A' para o vizinho,
# o Nó 1 ainda não sabe que 'evt_A' existe.
echo "🟠 [2/3] Enviando REPLY 'evt_B' (ref 'evt_A') para o Nó 1 (Bob)..."
echo "   (O Nó 1 provavelmente ainda não recebeu o 'evt_A' devido à latência simulada)"
curl -s -X POST http://localhost:8081/post \
-H "Content-Type: application/json" \
-d '{"processId": 1, "evtId": "evt_B", "parentEvtId": "evt_A", "author": "Bob", "text": "Concordo plenamente!"}'
echo ""

echo ""
echo "👀 Observe acima: O FEED DO PROCESSO 1 deve mostrar 'REPLIES ÓRFÃOS'"
echo "   Isso acontece porque ele tem a resposta, mas não a pergunta."
echo ""
echo "⏳ Aguardando propagação da rede (Consistência Eventual)..."
sleep 5

echo ""
echo "🟢 [3/3] Verificação Final"
echo "   O Nó 0 deve ter acordado e enviado o 'evt_A'."
echo "   O Nó 1 deve ter recebido 'evt_A' e movido o reply para o lugar certo."
echo "   Todos os nós devem ter convergido."
echo ""

# Mantém o script rodando para o usuário ver os logs finais ou brincar mais
read -p "Pressione [Enter] para matar os processos e sair..."