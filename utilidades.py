"""
Funciones compartidas por todos los scripts:
- descarga de los modelos de MediaPipe (solo la primera vez)
- apertura de la cámara con mensajes de error claros
- creación de detectores de manos y de cuerpo (API "Tasks" de MediaPipe)
- utilidades de dibujo y texto con OpenCV
"""
import os
import ssl
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

CARPETA = os.path.dirname(os.path.abspath(__file__))
CARPETA_MODELOS = os.path.join(CARPETA, "modelos")

MODELOS = {
    "manos": (
        "hand_landmarker.task",
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task",
    ),
    "pose": (
        "pose_landmarker_lite.task",
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    ),
}

# Conexiones entre los 21 puntos de la mano (para dibujar el esqueleto)
CONEXIONES_MANO = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


# ----------------------------------------------------------------------------
# Modelos
# ----------------------------------------------------------------------------
def obtener_modelo(nombre):
    """Regresa la ruta local del modelo; lo descarga si no existe."""
    archivo, url = MODELOS[nombre]
    os.makedirs(CARPETA_MODELOS, exist_ok=True)
    ruta = os.path.join(CARPETA_MODELOS, archivo)
    if os.path.exists(ruta) and os.path.getsize(ruta) > 100_000:
        return ruta  # ya descargado (un modelo real pesa varios MB)

    print(f"[modelo] Descargando {archivo} (solo la primera vez)...")
    try:
        urllib.request.urlretrieve(url, ruta)
    except Exception as error:
        # En Mac, el Python de python.org a veces no trae certificados SSL.
        try:
            import certifi

            contexto = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(url, context=contexto) as r, open(ruta, "wb") as f:
                f.write(r.read())
        except Exception:
            if os.path.exists(ruta):
                os.remove(ruta)
            raise SystemExit(
                f"\nNo se pudo descargar el modelo: {error}\n"
                f"Descárgalo a mano desde:\n  {url}\n"
                f"y guárdalo como:\n  {ruta}\n"
            )
    if os.path.getsize(ruta) < 100_000:
        os.remove(ruta)
        raise SystemExit(f"\nLa descarga de {archivo} salió incompleta. Revisa tu internet y vuelve a correr.\n")
    print("[modelo] Listo.")
    return ruta


def crear_detector_manos(num_manos=2):
    opciones = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=obtener_modelo("manos")),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=num_manos,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.HandLandmarker.create_from_options(opciones)


def crear_detector_pose():
    opciones = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=obtener_modelo("pose")),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return vision.PoseLandmarker.create_from_options(opciones)


def a_imagen_mp(frame_bgr):
    """OpenCV entrega BGR; MediaPipe espera RGB."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


class MarcaTiempo:
    """MediaPipe en modo VIDEO exige marcas de tiempo (ms) siempre crecientes."""

    def __init__(self):
        self.inicio = time.monotonic()
        self.ultimo = -1

    def ms(self):
        t = int((time.monotonic() - self.inicio) * 1000)
        if t <= self.ultimo:
            t = self.ultimo + 1
        self.ultimo = t
        return t


# ----------------------------------------------------------------------------
# Cámara
# ----------------------------------------------------------------------------
def abrir_camara(indice=0, ancho=1280, alto=720):
    cap = cv2.VideoCapture(indice)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
    if not cap.isOpened():
        raise SystemExit(
            "\nNo se pudo abrir la cámara.\n"
            "- En Mac: Ajustes del Sistema > Privacidad y seguridad > Cámara,\n"
            "  activa Terminal o Visual Studio Code y vuelve a abrirlo.\n"
            "- Cierra Zoom/Meet/FaceTime si están usando la cámara.\n"
            "- Prueba otro índice: python script.py --camara 1\n"
        )
    return cap


class ContadorFPS:
    def __init__(self):
        self.prev = time.monotonic()
        self.fps = 0.0

    def tick(self):
        ahora = time.monotonic()
        dt = ahora - self.prev
        self.prev = ahora
        if dt > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)
        return self.fps


# ----------------------------------------------------------------------------
# Texto y dibujo
# (cv2.putText NO soporta acentos ni ñ: por eso el texto en pantalla va sin ellos)
# ----------------------------------------------------------------------------
FUENTE = cv2.FONT_HERSHEY_SIMPLEX


def texto(img, msg, pos, escala=0.8, color=(255, 255, 255), grosor=2, fondo=(0, 0, 0), margen=8):
    (w, h), base = cv2.getTextSize(msg, FUENTE, escala, grosor)
    x, y = pos
    if fondo is not None:
        cv2.rectangle(img, (x - margen, y - h - margen), (x + w + margen, y + base + margen), fondo, -1)
    cv2.putText(img, msg, (x, y), FUENTE, escala, color, grosor, cv2.LINE_AA)
    return w, h


def texto_centrado(img, msg, centro, escala=1.0, color=(255, 255, 255), grosor=2, fondo=None, contorno=True):
    (w, h), _ = cv2.getTextSize(msg, FUENTE, escala, grosor)
    x, y = int(centro[0] - w / 2), int(centro[1] + h / 2)
    if fondo is not None:
        cv2.rectangle(img, (x - 12, y - h - 12), (x + w + 12, y + 12), fondo, -1)
    if contorno:
        cv2.putText(img, msg, (x, y), FUENTE, escala, (0, 0, 0), grosor + 4, cv2.LINE_AA)
    cv2.putText(img, msg, (x, y), FUENTE, escala, color, grosor, cv2.LINE_AA)


def dibujar_mano(img, puntos, color=(0, 255, 0)):
    """puntos: lista de 21 landmarks normalizados de MediaPipe."""
    h, w = img.shape[:2]
    pts = [(int(p.x * w), int(p.y * h)) for p in puntos]
    for a, b in CONEXIONES_MANO:
        cv2.line(img, pts[a], pts[b], color, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, p, 4, (255, 255, 255), -1, cv2.LINE_AA)
    return pts
