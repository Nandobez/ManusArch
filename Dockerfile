FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1

# Adicionar PPA do Mozilla para Firefox .deb (não snap)
RUN apt-get update && apt-get install -y software-properties-common wget gnupg
RUN install -d -m 0755 /etc/apt/keyrings
RUN wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null
RUN echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | tee /etc/apt/sources.list.d/mozilla.list > /dev/null
RUN echo 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000' | tee /etc/apt/preferences.d/mozilla

# Instalar dependencias base
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    firefox \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    supervisor \
    wget \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Criar diretorio de trabalho
WORKDIR /workspace

# Criar ambiente virtual Python
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar bibliotecas Python uteis
RUN pip install --no-cache-dir \
    requests \
    beautifulsoup4 \
    playwright \
    selenium

# Instalar browsers do Playwright
RUN playwright install firefox
RUN playwright install-deps firefox

# Configurar supervisor para gerenciar processos
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copiar scripts do sandbox
COPY sandbox_scripts/ /opt/sandbox_scripts/

# Script de inicializacao
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Portas: 5900=VNC, 6080=noVNC, 8888=Browser Server
EXPOSE 5900 6080 8888

CMD ["/start.sh"]
