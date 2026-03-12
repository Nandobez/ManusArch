#!/bin/bash

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CONTAINER_NAME="sandbox"
IMAGE_NAME="sandbox"

# Função de limpeza ao sair
cleanup() {
    echo -e "\n${YELLOW}Encerrando...${NC}"
    echo -e "${RED}Derrubando container ${CONTAINER_NAME}...${NC}"
    docker stop $CONTAINER_NAME 2>/dev/null
    docker rm $CONTAINER_NAME 2>/dev/null
    echo -e "${GREEN}Container encerrado.${NC}"
    exit 0
}

# Captura CTRL+C e outros sinais
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}              ManusArch - Iniciando Sistema                  ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"

# Verifica se a imagem existe
if ! docker image inspect $IMAGE_NAME &>/dev/null; then
    echo -e "${YELLOW}Imagem não encontrada. Construindo...${NC}"
    docker build -t $IMAGE_NAME "$(dirname "$0")"
fi

# Para container existente se houver
docker stop $CONTAINER_NAME 2>/dev/null
docker rm $CONTAINER_NAME 2>/dev/null

# Inicia o container
echo -e "${GREEN}Iniciando container...${NC}"
docker run -d --name $CONTAINER_NAME \
    -p 6080:6080 \
    -p 5900:5900 \
    -p 8888:8888 \
    -p 8080:8080 \
    $IMAGE_NAME

# Aguarda o container iniciar
echo -e "${YELLOW}Aguardando serviços iniciarem...${NC}"
sleep 3

# Verifica se browser server está rodando
for i in {1..10}; do
    if curl -s http://localhost:8888 &>/dev/null; then
        echo -e "${GREEN}Browser server pronto!${NC}"
        break
    fi
    echo "Aguardando browser server... ($i/10)"
    sleep 2
done

echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Container rodando!${NC}"
echo -e "${GREEN}  noVNC: http://localhost:6080${NC}"
echo -e "${GREEN}  Browser API: http://localhost:8888${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""

# Muda para o diretório do orquestrador e executa
cd "$(dirname "$0")/orchestrator"

# Executa o orquestrador (bloqueante)
python3 main.py

# Quando o orquestrador terminar, limpa
cleanup
