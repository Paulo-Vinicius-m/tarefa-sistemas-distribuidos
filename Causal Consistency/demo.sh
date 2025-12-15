#!/bin/bash

# ==============================================================================
# Script de Demonstração: Consistência Causal
# ==============================================================================
# Diferente da Consistência Eventual, aqui NÃO devemos ver "Replies Órfãos".
#
# Cenário:
# 1. Alice (Nó 0) cria um Post (atrasado na rede).
# 2. Injetamos uma Resposta (de um terceiro, Nó 2) diretamente no Nó 1.
# 3. O Nó 1 receberá a Resposta ANTES do Post original.
# 4. Resultado esperado: O Nó 1 segura a Resposta no BUFFER até o Post chegar.
# ==============================================================================

cleanup() {
    echo ""
    echo "🛑 Encerrando todos os nós..."
    kill $(jobs -p) 2>/dev/null
    wait
    echo "✅ Demo finalizada."
}

trap cleanup SIGINT EXIT

echo "🚀 Iniciando Cluster (Causal)..."

# Inicia os 3 processos
python app.py 0 &
PID0=$!
python app.py 1 &
PID1=$!
python app.py 2 &
PID2=$!

echo "⏳ Aguardando startup (5s)..."
sleep 5

echo ""
echo "============================================================"
echo "Cluster Operacional. Cenário: BUFFER DE CAUSALIDADE"
echo "============================================================"
echo ""

# 1. Alice posta no Nó 0
# O código Python tem um delay(3s) no Nó 0 antes de espalhar a mensagem.
echo "🔵 [1/3] Alice (Nó 0) posta 'evt_A'..."
echo "    -> O Nó 0 vê imediatamente, mas demora a enviar para o Nó 1."
curl -s -X POST http://localhost:8080/post \
-H "Content-Type: application/json" \
-d '{"processId": 0, "evtId": "evt_A", "author": "Alice", "text": "Post Original", "vector_clock": []}'
echo ""
echo ""

# 2. Simulação de "Fofoca Adiantada" no Nó 1
# Enviamos diretamente para o /share do Nó 1 uma mensagem vinda do Nó 2 (Carlos)
# que é uma RESPOSTA ao evt_A.
# Vector Clock simulado [1, 0, 1] significa: Carlos viu msg do Nó 0 e a sua própria.
echo "🟠 [2/3] Chega no Nó 1 uma Resposta 'evt_B' (vinda do Carlos/Nó 2)..."
echo "    -> O Nó 1 AINDA NÃO recebeu o 'evt_A' da Alice."
echo "    -> A Consistência Causal deve IMPEDIR que isso apareça no feed."

curl -s -X POST http://localhost:8081/share \
-H "Content-Type: application/json" \
-d '{"processId": 2, "evtId": "evt_B", "parentEvtId": "evt_A", "author": "Carlos", "text": "Resposta fofocada", "vector_clock": [1, 0, 1]}'

echo ""
echo ""
echo "👀 OLHE O FEED DO PROCESSO 1 ACIMA!"
echo "   Você deve ver: '>>> BUFFER DE ESPERA ... Motivo: Post pai <evt_A> ausente'"
echo "   A mensagem NÃO entrou no feed principal."
echo ""

echo "⏳ Aguardando a Alice (Nó 0) entregar a mensagem original (aprox 4s)..."
sleep 5

echo ""
echo "🟢 [3/3] O Post 'evt_A' finalmente chega no Nó 1."
echo "   O sistema deve detectar que a dependência foi satisfeita."
echo "   A mensagem 'evt_B' deve sair do Buffer automaticamente."
echo ""

# Mantém rodando
read -p "Pressione [Enter] para sair..."