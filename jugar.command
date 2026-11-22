#!/bin/bash
# Abre el juego. Uso:  bash jugar.command   (acepta opciones, p. ej. --control cuerpo)
set -o pipefail
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Primero corre:  bash instalar.command"
  exit 1
fi
.venv/bin/python -u 04_juego_globos.py "$@" 2>&1 | tee juego_log.txt
