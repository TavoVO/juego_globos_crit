#!/bin/bash
# ============================================================
#  Instalador del juego "Atrapa Globos" (macOS)
#  Uso:  bash instalar.command
#  Deja todo el detalle en instalacion_log.txt
# ============================================================
cd "$(dirname "$0")" || exit 1
LOG="instalacion_log.txt"
exec > >(tee "$LOG") 2>&1

fallar() {
  echo ""
  echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  echo "  ERROR: $1"
  echo "  El detalle quedo en: $(pwd)/$LOG"
  echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  exit 1
}

echo "== Instalando Atrapa Globos =="
date
sw_vers 2>/dev/null
echo "Procesador: $(uname -m)"
echo "Carpeta: $(pwd)"
echo ""

# ---------- 1. Buscar un Python compatible con MediaPipe (3.10 - 3.12 ideal) ----------
PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
for d in /Library/Frameworks/Python.framework/Versions/*/bin; do PATH="$d:$PATH"; done

PY=""
for c in python3.12 python3.11 python3.10 python3.13 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
    echo "Encontrado $c -> version $v ($(command -v "$c"))"
    case "$v" in
      3.10|3.11|3.12|3.13) PY="$c"; break ;;
    esac
  fi
done

if [ -z "$PY" ] && command -v brew >/dev/null 2>&1; then
  echo ""
  echo "No hay un Python compatible. Instalando Python 3.12 con Homebrew..."
  brew install python@3.12 && PY="$(brew --prefix)/bin/python3.12"
fi

if [ -z "$PY" ]; then
  echo ""
  echo "Se necesita Python 3.12. Abriendo la pagina de descarga..."
  echo "Descarga 'macOS 64-bit universal2 installer', instalalo y vuelve a correr:"
  echo "   bash instalar.command"
  open "https://www.python.org/downloads/release/python-3129/"
  fallar "No se encontro Python 3.10 - 3.13"
fi
echo ""
echo "Usando: $PY ($("$PY" --version))"

# ---------- 2. Ambiente virtual ----------
if [ -d .venv ]; then
  if ! .venv/bin/python -c "import sys" >/dev/null 2>&1; then
    echo "El ambiente .venv esta danado, se vuelve a crear."
    mv .venv ".venv_viejo_$(date +%s)"
  fi
fi
if [ ! -d .venv ]; then
  echo "Creando ambiente virtual .venv ..."
  "$PY" -m venv .venv || fallar "No se pudo crear el ambiente virtual"
fi
# shellcheck disable=SC1091
source .venv/bin/activate || fallar "No se pudo activar .venv"
echo "Python del ambiente: $(python --version) en $(command -v python)"

# ---------- 3. Librerias ----------
echo ""
echo "Instalando librerias (puede tardar unos minutos)..."
python -m pip install --upgrade pip || fallar "No se pudo actualizar pip (revisa tu internet)"
python -m pip install -r requirements.txt || fallar "Fallo la instalacion de librerias"
# opencv-python y opencv-contrib-python juntos se estorban (los dos son "cv2")
if python -m pip show opencv-python >/dev/null 2>&1; then
  echo "Quitando opencv-python duplicado..."
  python -m pip uninstall -y opencv-python
  python -m pip install --force-reinstall --no-deps opencv-contrib-python || fallar "No se pudo reinstalar OpenCV"
fi

echo ""
python - <<'EOF' || fallar "Las librerias se instalaron pero no cargan"
import cv2, mediapipe, numpy, PIL
print("OK opencv", cv2.__version__, "| mediapipe", mediapipe.__version__,
      "| numpy", numpy.__version__, "| pillow", PIL.__version__)
from mediapipe.tasks.python import vision
print("OK API de MediaPipe Tasks disponible")
EOF

# ---------- 4. Modelos de MediaPipe ----------
echo ""
echo "Descargando modelos de MediaPipe..."
mkdir -p modelos
if ! python -c "import utilidades as U; print(U.obtener_modelo('manos')); print(U.obtener_modelo('pose'))"; then
  echo "Intentando descargar con curl..."
  curl -fL -o modelos/hand_landmarker.task \
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task" &&
  curl -fL -o modelos/pose_landmarker_lite.task \
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task" \
    || fallar "No se pudieron descargar los modelos (revisa tu internet)"
fi

# ---------- 5. Prueba de los detectores y de los graficos ----------
python - <<'EOF' || fallar "Los detectores no arrancaron"
import numpy as np, utilidades as U, graficos as G
img = U.a_imagen_mp(np.zeros((480, 640, 3), np.uint8))
m = U.crear_detector_manos(); m.detect_for_video(img, 0); m.close()
p = U.crear_detector_pose(); p.detect_for_video(img, 0); p.close()
G.sprite_globero(460); G.sprite_texto("¡Listo!", 40)
print("OK detectores de manos y cuerpo funcionando")
print("OK graficos, fuente:", getattr(G.fuente(20), "path", "por defecto"))
EOF

echo ""
echo "======================================================"
echo "  INSTALACION COMPLETA"
echo "  Para jugar:  bash jugar.command"
echo "  (la primera vez macOS pedira permiso de camara para"
echo "   la Terminal: acepta y vuelve a abrir el juego)"
echo "======================================================"
