#!/bin/bash

# Criar diretorio do fluxbox se nao existir
mkdir -p ~/.fluxbox

# Iniciar supervisor (gerencia todos os processos)
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
