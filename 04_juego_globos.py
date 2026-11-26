"""
PASO 4 - JUEGO: Atrapa globos y llévalos a la mano del globero.

Cómo se juega
-------------
1. En el menú, pon el dedo sobre una tarjeta (Colores, Formas o Letras)
   hasta que se llene la barra. Elige cuántas opciones quieres usar para iniciar
   la cuenta regresiva 3, 2, 1.
2. Abre el pulgar y el índice, apunta a un globo y júntalos para atraparlo.
3. Mantén la pinza cerrada y llévalo al globero. Abre los dedos para soltarlo.
4. El globero pide un globo en su burbuja. Si entregas el correcto ganas
   puntos y confeti; si no, el globo se revienta y te recuerda cuál buscar
   (sin restar puntos).

En el menú puedes elegir la velocidad y ver la cámara como fondo o en un
recuadro. El historial guarda las partidas terminadas en esta computadora.

Ejecutar:  python 04_juego_globos.py
Opciones:  --tiempo 90   --globos 4   --control mano|cuerpo   --sin-sonido
Teclas:    1/2/3 = elegir modo y cantidad   ESPACIO = continuar   M = menú   R = reiniciar
           P/ESPACIO = pausar/continuar   T = terminar partida
           F = pantalla completa    H = mostrar/ocultar mano    Q o ESC = salir
"""
import argparse
import math
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Permite ejecutar este archivo directamente con el Python elegido en VS Code.
# Las dependencias ya están instaladas en el entorno local del proyecto.
if __name__ == "__main__":
    entorno = Path(__file__).resolve().parent / ".venv"
    python_local = entorno / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # macOS admite distintas representaciones Unicode de la misma ruta.
    # Comparar archivos evita relanzar sin fin cuando la carpeta tiene acentos.
    if python_local.is_file() and not os.path.samefile(sys.prefix, entorno):
        print("Usando el entorno del juego (.venv)...", flush=True)
        os.execv(str(python_local), [str(python_local), str(Path(__file__).resolve()), *sys.argv[1:]])

import cv2
import mediapipe as mp
import numpy as np

import graficos as G
import utilidades as U
from puntuaciones import Historial, Puntuacion, SIN_NOMBRE

VENTANA = "Atrapa Globos - CRIT"
ANCHO_LIENZO = 1280
LADO_MAX_DETECCION = 1280
UMBRAL_CERRAR_PINZA = 0.39
UMBRAL_ABRIR_PINZA = 0.55
MEMORIA_MANO_ABIERTA = 0.18  # segundos para tolerar un fotograma perdido al cerrar
TIEMPO_ABRIR_PARA_SOLTAR = 0.07

COLORES = G.COLORES_GLOBO
MODOS = {1: "COLORES", 2: "FORMAS", 3: "LETRAS"}
CAMPO = {"COLORES": "color", "FORMAS": "forma", "LETRAS": "letra"}
OPCIONES = {"COLORES": tuple(COLORES), "FORMAS": G.FORMAS_GLOBO, "LETRAS": G.LETRAS_GLOBO}
NOMBRES_OPCIONES = {"COLORES": ("color", "colores"), "FORMAS": ("figura", "figuras"), "LETRAS": ("letra", "letras")}
VELOCIDADES = {"Lenta": 0.6, "Normal": 1.0, "Rápida": 1.6}
VISTAS = ("Cámara", "Fondo")
FONDO_PARQUE = Path(__file__).resolve().parent / "recursos" / "parque.jpg"
FILAS_HISTORIAL = 7
MAX_NOMBRE = 30

FELICITACIONES = ["¡Muy bien!", "¡Excelente!", "¡Genial!", "¡Lo lograste!", "¡Bravo!"]


# ----------------------------------------------------------------------------
# Sonido (usa los sonidos que ya trae macOS; en otros sistemas queda en silencio)
# ----------------------------------------------------------------------------
class Sonido:
    ARCHIVOS = {"agarrar": "Pop", "bien": "Glass", "mal": "Submarine",
                "cuenta": "Tink", "ya": "Ping", "fin": "Hero"}

    def __init__(self, activo):
        self.activo = activo and sys.platform == "darwin"

    def __call__(self, nombre):
        if not self.activo:
            return
        ruta = f"/System/Library/Sounds/{self.ARCHIVOS[nombre]}.aiff"
        if os.path.exists(ruta):
            try:
                subprocess.Popen(["afplay", ruta], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self.activo = False


# ----------------------------------------------------------------------------
# Globo
# ----------------------------------------------------------------------------
class Globo:
    def __init__(self, x_min, x_max, alto, escala, atributo_fijo, carril):
        self.x_min, self.x_max, self.alto, self.S = x_min, x_max, alto, escala
        self.carril = carril
        self.color = "AZUL"    # Las formas y letras se distinguen por el símbolo.
        setattr(self, *atributo_fijo)
        self.reiniciar(primera_vez=True)

    def reiniciar(self, primera_vez=False):
        self.r = int(random.randint(46, 58) * self.S)
        x_min, x_max = self.x_min + self.r, self.x_max - self.r
        self.x = x_min + (x_max - x_min) * self.carril
        if primera_vez:
            self.y = random.uniform(self.alto * 0.42, self.alto * 0.73)
        else:
            self.y = random.uniform(self.alto * 0.76, self.alto * 0.85)
        self.vy = random.uniform(45, 80) * self.S
        self.fase = random.uniform(0, 2 * math.pi)
        self.x_osc = 0.0
        self.agarrado = False

    def atributo(self, modo):
        return getattr(self, CAMPO[modo])

    def actualizar(self, dt, t, velocidad=1.0):
        if not self.agarrado:
            self.y -= self.vy * dt * velocidad
            self.x_osc = 14 * self.S * math.sin(t * 1.4 + self.fase)
            if self.y < -self.r * 0.5:
                self.reiniciar()

    def centro(self):
        return int(self.x + (0 if self.agarrado else self.x_osc)), int(self.y)

    def contiene(self, p):
        cx, cy = self.centro()
        return math.hypot(p[0] - cx, p[1] - cy) < self.r * 1.35

    def visible(self):
        return -self.r < self.y < self.alto - self.r * 0.5

    def dibujar(self, img, modo, t):
        tipo = modo if modo in ("FORMAS", "LETRAS") else None
        simbolo = self.atributo(modo) if tipo else None
        spr, ax, ay, ky = G.sprite_globo(COLORES[self.color], self.r, tipo, simbolo)
        cx, cy = self.centro()
        # hilo ondulado
        y0 = cy + (ky - ay)
        pts = [(cx, int(y0))]
        for i in range(1, 8):
            pts.append((int(cx + 5 * self.S * math.sin(t * 3 + self.fase + i * 0.9)), int(y0 + i * 11 * self.S)))
        cv2.polylines(img, [np.array(pts, np.int32)], False, (235, 235, 235), max(1, int(2 * self.S)), cv2.LINE_AA)
        G.pegar(img, spr, cx - ax, cy - ay)


# ----------------------------------------------------------------------------
# Efectos: confeti, reventones y puntos flotantes
# ----------------------------------------------------------------------------
class Efectos:
    def __init__(self, escala):
        self.S = escala
        self.particulas = []   # [x, y, vx, vy, ang, vang, color_bgr, tam, vida, vida_max]
        self.textos = []       # [sprite, x, y, t0, duracion]
        self.aros = []         # [x, y, color_bgr, t0]

    def confeti(self, x, y, n=45):
        paleta = [G.bgr(c) for c in COLORES.values()] + [(255, 255, 255)]
        for _ in range(n):
            ang = random.uniform(0, 2 * math.pi)
            vel = random.uniform(220, 620) * self.S
            vida = random.uniform(0.9, 1.6)
            self.particulas.append([x, y, math.cos(ang) * vel, math.sin(ang) * vel - 320 * self.S,
                                    random.uniform(0, 6.28), random.uniform(-10, 10), random.choice(paleta),
                                    random.uniform(7, 13) * self.S, vida, vida])

    def reventar(self, x, y, rgb):
        col = G.bgr(rgb)
        self.aros.append([x, y, col, time.monotonic()])
        for _ in range(18):
            ang = random.uniform(0, 2 * math.pi)
            vel = random.uniform(150, 380) * self.S
            self.particulas.append([x, y, math.cos(ang) * vel, math.sin(ang) * vel, random.uniform(0, 6.28),
                                    random.uniform(-12, 12), col, random.uniform(8, 14) * self.S, 0.6, 0.6])

    def texto(self, sprite, x, y, duracion=1.0):
        self.textos.append([sprite, x, y, time.monotonic(), duracion])

    def actualizar_y_dibujar(self, img, dt, ahora=None):
        ahora = time.monotonic() if ahora is None else ahora
        vivas = []
        for p in self.particulas:
            p[3] += 900 * self.S * dt
            if dt > 0:
                p[2] *= 0.985
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] += p[5] * dt
            p[8] -= dt
            if p[8] <= 0:
                continue
            vivas.append(p)
            w, h = p[7], p[7] * 0.55 * abs(math.cos(p[4] * 0.7)) + 1
            c, s = math.cos(p[4]), math.sin(p[4])
            esquinas = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
            pts = np.array([(p[0] + a * c - b * s, p[1] + a * s + b * c) for a, b in esquinas], np.int32)
            cv2.fillConvexPoly(img, pts, p[6], cv2.LINE_AA)
        self.particulas = vivas

        self.aros = [a for a in self.aros if ahora - a[3] < 0.3]
        for x, y, col, t0 in self.aros:
            k = (ahora - t0) / 0.3
            cv2.circle(img, (int(x), int(y)), int((30 + 70 * k) * self.S), col, max(1, int(8 * (1 - k))), cv2.LINE_AA)

        self.textos = [t for t in self.textos if ahora - t[3] < t[4]]
        for spr, x, y, t0, dur in self.textos:
            k = (ahora - t0) / dur
            G.pegar_centro(img, spr, x, y - 80 * self.S * k, alpha=min(1.0, 2.5 * (1 - k)))


# ----------------------------------------------------------------------------
# Entrada: dedo índice (manos) o muñecas (cuerpo)
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Cursor:
    posicion: tuple
    identidad: str
    pinza: bool
    indice: tuple | None = None
    mano_detectada: bool = True


def leer_cursores(res, w, h, control, pinzas_previas, res_manos=None):
    """Pinza relativa al tamaño de la palma, con histéresis para evitar temblores."""
    cursores, manos = [], []
    resultado_manos = res if control == "mano" else res_manos
    estados = {}
    if resultado_manos is not None:
        for i, mano in enumerate(resultado_manos.hand_landmarks):
            coordenadas = [(p.x * w, p.y * h) for p in mano]
            pts = [(round(x), round(y)) for x, y in coordenadas]
            manos.append(pts)
            etiquetas = resultado_manos.handedness[i]
            identidad = etiquetas[0].category_name if etiquetas else f"mano-{i}"
            if identidad in estados:
                identidad = f"{identidad}-{i}"
            palma = max(math.dist(coordenadas[0], coordenadas[9]), math.dist(coordenadas[5], coordenadas[17]), 1)
            umbral = UMBRAL_ABRIR_PINZA if pinzas_previas.get(identidad, False) else UMBRAL_CERRAR_PINZA
            pinza = math.dist(coordenadas[4], coordenadas[8]) / palma < umbral
            estados[identidad] = pinza
            # El punto de pinza queda entre las dos yemas.
            posicion = tuple((a + b) // 2 for a, b in zip(pts[4], pts[8])) if pinza else pts[8]
            cursores.append(Cursor(posicion, identidad, pinza, indice=pts[8]))
    pinzas_previas.clear()
    pinzas_previas.update(estados)
    if control == "cuerpo":
        munecas = []
        for cuerpo in res.pose_landmarks:
            for idx in (15, 16):
                p = cuerpo[idx]
                vis = p.visibility if p.visibility is not None else 1.0
                if vis > 0.5:
                    munecas.append((idx, (int(p.x * w), int(p.y * h))))
        # Una detección de mano puede activar una sola muñeca.
        parejas = sorted((math.dist(posicion, pts[0]), idx, mano) for idx, posicion in munecas
                         for mano, pts in enumerate(manos))
        asignadas, usadas = {}, set()
        alcance = 0.15 * math.hypot(w, h)
        for distancia, idx, mano in parejas:
            if distancia < alcance and idx not in asignadas and mano not in usadas:
                asignadas[idx] = cursores[mano]
                usadas.add(mano)
        cursores = [Cursor(posicion, f"muneca-{idx}", asignadas[idx].pinza, indice=asignadas[idx].indice)
                    if idx in asignadas else Cursor(posicion, f"muneca-{idx}", False, mano_detectada=False)
                    for idx, posicion in munecas]
    return cursores, manos


def dibujar_manos(img, manos, escala):
    for pts in manos:
        for a, b in U.CONEXIONES_MANO:
            cv2.line(img, pts[a], pts[b], (255, 255, 255), max(2, int(3 * escala)), cv2.LINE_AA)
        for i, p in enumerate(pts):
            cv2.circle(img, p, max(3, int(5 * escala)), (255, 200, 60) if i % 4 else (255, 255, 255), -1, cv2.LINE_AA)


def dibujar_cursor(img, c, t, escala, activo=False):
    col = (90, 230, 255) if not activo else (40, 220, 120)
    G.pegar_centro(img, G.sprite_brillo(int(46 * escala), (255, 230, 90) if not activo else (120, 255, 150)), *c, alpha=0.8)
    r = int((20 + 2 * math.sin(t * 6)) * escala)
    cv2.circle(img, c, r, (255, 255, 255), max(2, int(4 * escala)), cv2.LINE_AA)
    cv2.circle(img, c, max(3, int(6 * escala)), col, -1, cv2.LINE_AA)


def arco(img, centro, radio, fraccion, color, grosor, fondo=(60, 60, 60)):
    cv2.ellipse(img, centro, (radio, radio), -90, 0, 360, fondo, grosor, cv2.LINE_AA)
    if fraccion > 0:
        cv2.ellipse(img, centro, (radio, radio), -90, 0, 360 * min(1.0, fraccion), color, grosor, cv2.LINE_AA)


# ----------------------------------------------------------------------------
# Juego
# ----------------------------------------------------------------------------
class Juego:
    def __init__(self, w, h, duracion, n_globos, sonido, archivo_historial=None):
        self.w, self.h = w, h
        self.S = S = min(h / 720, w / 1280)   # escala para cualquier resolución
        self.duracion, self.n_globos = duracion, n_globos
        self.cantidades = range(1, min(3, n_globos or 3) + 1)
        self.cantidad = max(self.cantidades)
        self.sonido = sonido
        self.efectos = Efectos(S)
        self.historial = Historial(archivo_historial)
        self.nombre = ""
        self.borrador_nombre = None
        self.velocidad = "Normal"
        self.vista = "Cámara"

        self.spr_globero, mx, my = G.sprite_globero(int(290 * S))
        gh, gw = self.spr_globero.shape[:2]
        self.pos_globero = (w - gw - int(24 * S), h - gh - int(242 * S))
        self.zona = (self.pos_globero[0] + int(mx), self.pos_globero[1] + int(my))
        self.radio_zona = int(62 * S)
        self.x_max_globos = min(self.zona[0] - self.radio_zona - int(30 * S), w - int(385 * S))
        self.centro_juego = self.x_max_globos // 2

        # tarjetas del menú
        tw, th, sep = int(226 * S), int(190 * S), int(22 * S)
        x0 = self.centro_juego - (3 * tw + 2 * sep) // 2
        self.tarjetas = {modo: (x0 + i * (tw + sep), int(222 * S), tw, th) for i, modo in enumerate(MODOS.values())}
        cw, ch, espacio = int(208 * S), int(147 * S), int(18 * S)
        ancho = len(self.cantidades) * cw + (len(self.cantidades) - 1) * espacio
        x_cantidad = self.centro_juego - ancho // 2
        self.tarjetas_cantidad = {n: (x_cantidad + i * (cw + espacio), h // 2 - int(51 * S), cw, ch)
                                  for i, n in enumerate(self.cantidades)}
        self.volver_cantidad = (self.centro_juego - int(105 * S), h // 2 + int(120 * S), int(210 * S), int(50 * S))
        self.ajustes = {}
        for y, opciones in ((448, VELOCIDADES), (510, VISTAS)):
            for i, opcion in enumerate(opciones):
                x = x0 + int((144 + i * 140) * S)
                self.ajustes[opcion] = (x, int(y * S), int(128 * S), int(47 * S))
        self.campo_nombre = (x0 + int(144 * S), int(572 * S), int(408 * S), int(47 * S))
        self.acceso_historial = (x0, int(640 * S), int(234 * S), int(52 * S))
        self.rect_camara = (w - int(368 * S), h - int(220 * S), int(350 * S), int(202 * S))
        # botones de la pantalla final
        bw, bh, espacio = int(190 * S), int(62 * S), int(13 * S)
        cy = h // 2 + int(175 * S)
        x_fin = w // 2 - (3 * bw + 2 * espacio) // 2
        self.botones = {clave: (x_fin + i * (bw + espacio), cy, bw, bh) for i, clave in
                        enumerate(("otra", "historial", "menu"))}
        y_historial = h // 2 + int(220 * S)
        self.botones_historial = {
            "volver": (w // 2 - int(425 * S), y_historial, int(170 * S), int(52 * S)),
            "anterior": (w // 2 + int(100 * S), y_historial, int(150 * S), int(52 * S)),
            "siguiente": (w // 2 + int(275 * S), y_historial, int(150 * S), int(52 * S)),
        }
        self.controles = {
            "pausa": (int(18 * S), h - int(64 * S), int(220 * S), int(48 * S)),
            "terminar": (int(252 * S), h - int(64 * S), int(220 * S), int(48 * S)),
        }
        self.pinzas_listas = {}
        self.bloqueo_controles = False
        self.t_animacion = 0.0
        self.dwell_ui = {}
        self.modo = "COLORES"
        self.ir_menu()

    # --- estados ------------------------------------------------------------
    def ir_menu(self):
        self.estado = "menu"
        self.dwell_ui = {}
        self.preparar_partida(self.modo)

    def preparar_partida(self, modo):
        self.modo = modo
        self.puntos = self.aciertos = self.errores = self.racha = self.mejor_racha = 0
        self.entregados = []
        valores = OPCIONES[modo][:self.cantidad]
        valores = random.sample(valores, len(valores))
        total_globos = self.n_globos or self.cantidad
        self.globos = [Globo(int(30 * self.S), self.x_max_globos, self.h, self.S,
                             (CAMPO[modo], valores[i % len(valores)]), (i + 0.5) / total_globos)
                       for i in range(total_globos)]
        self.sostenido = None
        self.dueno_globo = None
        self.perdido = 0.0
        self.t_abierta = 0.0
        self.mensaje = None
        self.destello_hasta = 0.0
        self.dwell_ui = {}
        self.bloqueo_controles = False
        self.objetivo = None
        self.nuevo_objetivo()

    def iniciar_cuenta(self, modo, cantidad=None):
        if cantidad is not None:
            self.cantidad = cantidad
        self.preparar_partida(modo)
        self.estado = "cuenta"
        self.t_cuenta = time.monotonic()
        self.ultimo_numero = None

    def empezar(self):
        self.estado = "jugando"
        self.inicio = time.monotonic()

    def terminar(self):
        if self.estado == "jugando" or (self.estado == "pausa" and self.estado_antes_pausa == "jugando"):
            self.historial.agregar(Puntuacion(
                fecha=datetime.now().strftime("%d/%m/%y %H:%M"), categoria=self.modo.capitalize(),
                velocidad=self.velocidad, puntos=self.puntos, aciertos=self.aciertos, nombre=self.nombre or SIN_NOMBRE,
            ))
        self.estado = "fin"
        self.dwell_ui = {}
        self.soltar()
        self.sonido("fin")

    def alternar_pausa(self):
        ahora = time.monotonic()
        if self.estado in ("jugando", "cuenta"):
            self.estado_antes_pausa = self.estado
            self.t_pausa = ahora
            self.estado = "pausa"
        elif self.estado == "pausa":
            duracion_pausa = ahora - self.t_pausa
            if self.estado_antes_pausa == "jugando":
                self.inicio += duracion_pausa
            else:
                self.t_cuenta += duracion_pausa
            self.destello_hasta += duracion_pausa
            if self.mensaje:
                self.mensaje = (self.mensaje[0], self.mensaje[1] + duracion_pausa)
            for efecto in self.efectos.aros:
                efecto[3] += duracion_pausa
            for efecto in self.efectos.textos:
                efecto[3] += duracion_pausa
            self.estado = self.estado_antes_pausa
        self.dwell_ui = {}
        self.bloqueo_controles = True

    def botones_visibles(self):
        if self.estado == "menu":
            return {**self.tarjetas, **self.ajustes, "historial": self.acceso_historial}
        if self.estado == "cantidad":
            return {**self.tarjetas_cantidad, "menu": self.volver_cantidad}
        if self.estado == "fin":
            return self.botones
        if self.estado == "historial":
            visibles = {"volver": self.botones_historial["volver"]}
            if self.pagina_historial > 0:
                visibles["anterior"] = self.botones_historial["anterior"]
            if self.pagina_historial + 1 < self.paginas_historial():
                visibles["siguiente"] = self.botones_historial["siguiente"]
            return visibles
        return self.controles

    def paginas_historial(self):
        return max(1, math.ceil(len(self.historial.partidas) / FILAS_HISTORIAL))

    @staticmethod
    def dentro(posicion, rect):
        x, y, w, h = rect
        return x <= posicion[0] < x + w and y <= posicion[1] < y + h

    def activar_boton(self, clave):
        self.dwell_ui = {}
        if clave in self.tarjetas:
            self.modo_elegido = clave
            self.estado = "cantidad"
        elif self.estado == "cantidad" and clave in self.tarjetas_cantidad:
            self.iniciar_cuenta(self.modo_elegido, clave)
        elif clave in VELOCIDADES:
            self.velocidad = clave
        elif clave in VISTAS:
            self.vista = clave
        elif clave == "pausa":
            self.alternar_pausa()
        elif clave == "terminar":
            self.terminar()
        elif clave == "otra":
            self.iniciar_cuenta(self.modo)
        elif clave == "menu":
            self.ir_menu()
        elif clave == "historial":
            self.regreso_historial = self.estado
            self.pagina_historial = 0
            self.estado = "historial"
        elif clave == "volver":
            self.estado = self.regreso_historial
        elif clave == "anterior":
            self.pagina_historial -= 1
        elif clave == "siguiente":
            self.pagina_historial += 1
        # Evita repetir la acción si el dedo sigue sobre el botón.
        self.bloqueo_controles = True

    def clic(self, x, y):
        if self.estado == "menu":
            if self.dentro((x, y), self.campo_nombre):
                if self.borrador_nombre is None:
                    self.borrador_nombre = self.nombre
                    self.dwell_ui = {}
                return
            self.confirmar_nombre()
        for clave, rect in self.botones_visibles().items():
            if self.dentro((x, y), rect):
                self.activar_boton(clave)
                return

    def confirmar_nombre(self):
        if self.borrador_nombre is not None:
            self.nombre = " ".join(self.borrador_nombre.split())
            self.borrador_nombre = None

    def escribir_nombre(self, tecla):
        """Mientras se edita el nombre, las letras no activan atajos del juego."""
        if self.borrador_nombre is None:
            return False
        if tecla in (10, 13):
            self.confirmar_nombre()
        elif tecla == 27:
            self.borrador_nombre = None
        elif tecla in (8, 127):
            self.borrador_nombre = self.borrador_nombre[:-1]
        elif 32 <= tecla <= 0x24F and len(self.borrador_nombre) < MAX_NOMBRE:
            # Los backends nativos devuelven códigos distintos para teclas especiales.
            # Esta franja cubre letras latinas y evita interpretar flechas como texto.
            caracter = chr(tecla)
            if caracter.isalnum() or caracter in " -'":
                self.borrador_nombre += caracter
        return True

    def sobre_controles(self, posicion):
        return any(self.dentro(posicion, rect) for rect in self.controles.values())

    # --- lógica -------------------------------------------------------------
    def nuevo_objetivo(self):
        disponibles = [g.atributo(self.modo) for g in self.globos if g.visible()]
        if not disponibles:
            disponibles = [g.atributo(self.modo) for g in self.globos]
        self.objetivo = random.choice([valor for valor in disponibles if valor != self.objetivo] or disponibles)

    def avisar(self, texto, color, segundos=1.4):
        self.mensaje = (G.sprite_pildora(texto, int(34 * self.S), color), time.monotonic() + segundos)

    def tiempo_restante(self):
        ahora = self.t_pausa if self.estado == "pausa" else time.monotonic()
        return max(0.0, self.duracion - (ahora - self.inicio))

    def hover(self, clave, rect, cursores, dt, segundos=1.2):
        """Indica si el cursor lleva suficiente tiempo encima del botón."""
        dentro = any(self.dentro(c.posicion, rect) for c in cursores)
        p = self.dwell_ui.get(clave, 0.0)
        p = p + dt if dentro else max(0.0, p - 2 * dt)
        self.dwell_ui[clave] = p
        return p >= segundos

    def actualizar(self, cursores, dt, t):
        ahora = time.monotonic()
        self.pinzas_listas = {mano: visto for mano, visto in self.pinzas_listas.items()
                              if ahora - visto <= MEMORIA_MANO_ABIERTA}
        nuevas_pinzas = []
        for c in cursores:
            if not c.mano_detectada:
                continue
            if not c.pinza:
                self.pinzas_listas[c.identidad] = ahora
            elif self.pinzas_listas.pop(c.identidad, None) is not None:
                nuevas_pinzas.append(c)

        if self.borrador_nombre is not None:
            return
        botones = self.botones_visibles()
        if self.bloqueo_controles:
            self.bloqueo_controles = any(self.dentro(c.posicion, rect) for c in cursores for rect in botones.values())
        else:
            for clave, rect in botones.items():
                if self.hover(clave, rect, cursores, dt):
                    self.activar_boton(clave)
                    return
        if self.estado in ("pausa", "historial"):
            return
        self.t_animacion += dt
        t = self.t_animacion
        if self.estado in ("menu", "cantidad", "fin"):
            return

        if self.estado == "cuenta":
            transcurrido = ahora - self.t_cuenta
            numero = 3 - int(transcurrido / 0.8)
            if numero != self.ultimo_numero:
                self.ultimo_numero = numero
                self.sonido("cuenta" if numero > 0 else "ya")
            if transcurrido > 3 * 0.8 + 0.6:
                self.empezar()
            return

        # --- jugando ---
        if self.tiempo_restante() <= 0:
            self.terminar()
            return
        # Probar la pinza antes de mover lo que se veía en el cuadro anterior.
        if self.sostenido is None:
            self.agarrar_globo(nuevas_pinzas)
        else:
            self.mover_globo(cursores, dt, ahora)
        for g in self.globos:
            g.actualizar(dt, t, VELOCIDADES[self.velocidad])

    def agarrar_globo(self, nuevas_pinzas):
        for cursor in nuevas_pinzas:
            if self.sobre_controles(cursor.posicion):
                continue
            for punto in (cursor.posicion, cursor.indice):
                if punto is None or self.sobre_controles(punto):
                    continue
                opciones = [g for g in self.globos if g.contiene(punto)]
                if opciones:
                    g = min(opciones, key=lambda globo: math.dist(punto, globo.centro()))
                    g.x, g.y = g.centro()
                    g.x_osc = 0.0
                    self.desfase_agarre = (g.x - cursor.posicion[0], g.y - cursor.posicion[1])
                    g.agarrado, self.sostenido = True, g
                    self.dueno_globo = cursor.identidad
                    self.sonido("agarrar")
                    return

    def mover_globo(self, cursores, dt, ahora):
        g = self.sostenido
        propietario = next((c for c in cursores if c.identidad == self.dueno_globo), None)
        if propietario is None or not propietario.mano_detectada:
            self.perdido += dt
            self.t_abierta = 0.0
            if self.perdido > 1.0:                  # se perdió la mano: soltar el globo
                self.soltar()
            return
        self.perdido = 0.0
        if not propietario.pinza:
            ya_abierta = self.t_abierta > 0.0
            self.t_abierta += dt
            if ya_abierta and self.t_abierta >= TIEMPO_ABRIR_PARA_SOLTAR:
                self.soltar()
            return
        self.t_abierta = 0.0
        cx, cy = propietario.posicion
        # Conserva el punto de contacto y sigue el cursor sin suavizado adicional.
        g.x, g.y = cx + self.desfase_agarre[0], cy + self.desfase_agarre[1]
        if math.hypot(cx - self.zona[0], cy - self.zona[1]) < self.radio_zona + 15 * self.S:
            self.entregar(g, ahora)

    def soltar(self):
        if self.sostenido is not None:
            self.sostenido.agarrado = False
        self.sostenido = None
        self.dueno_globo = None
        self.perdido = 0.0
        self.t_abierta = 0.0

    def entregar(self, g, ahora):
        x, y = g.centro()
        self.soltar()
        if g.atributo(self.modo) == self.objetivo:
            self.racha += 1
            self.mejor_racha = max(self.mejor_racha, self.racha)
            self.aciertos += 1
            ganados = 10 + 5 * min(self.racha - 1, 4)   # bono por racha (máx +20)
            self.puntos += ganados
            self.entregados.append(g.color)
            self.destello_hasta = ahora + 0.7
            self.efectos.confeti(*self.zona)
            self.efectos.texto(G.sprite_texto(f"+{ganados}", int(48 * self.S), G.DORADO, 3), *self.zona)
            self.avisar(random.choice(FELICITACIONES) if self.racha < 3 else f"¡Racha de {self.racha}!",
                        (40, 170, 80))
            self.sonido("bien")
            g.reiniciar()
            self.nuevo_objetivo()
        else:
            self.racha = 0
            self.errores += 1
            self.efectos.reventar(x, y, COLORES[g.color])
            self.avisar(f"Ese es {g.atributo(self.modo).lower()}, busca {self.objetivo.lower()}",
                        (235, 130, 20), 2.2)
            self.sonido("mal")
            g.reiniciar()

    # --- dibujo -------------------------------------------------------------
    def dibujar(self, img, cursores, manos, t, dt, mostrar_manos, imagen_camara=None):
        S = self.S
        t = self.t_animacion
        ahora = self.t_pausa if self.estado == "pausa" else time.monotonic()

        if self.estado == "historial":
            self.dibujar_historial(img)
            for c in cursores:
                dibujar_cursor(img, c.posicion, t, S, activo=c.pinza)
            return

        self.dibujar_ramo(img, t)
        G.pegar(img, self.spr_globero, *self.pos_globero)
        if self.estado in ("jugando", "cuenta", "pausa"):
            self.dibujar_zona(img, t, ahora < self.destello_hasta)

        if self.estado not in ("menu", "cantidad"):
            for g in self.globos:
                if g is not self.sostenido:
                    g.dibujar(img, self.modo, t)
        if self.sostenido is not None:
            g = self.sostenido
            c = g.centro()
            self.linea_guia(img, (c[0], c[1] + g.r), self.zona, t)
            G.pegar_centro(img, G.sprite_brillo(int(g.r * 1.7), (255, 240, 140)), *c, alpha=0.9)
            g.dibujar(img, self.modo, t)

        self.efectos.actualizar_y_dibujar(img, 0 if self.estado == "pausa" else dt, ahora)

        if self.estado == "menu":
            self.dibujar_menu(img, t)
        elif self.estado == "cantidad":
            self.dibujar_cantidad(img)
        elif self.estado == "cuenta":
            self.dibujar_hud(img, t, cuenta=True)
            self.dibujar_cuenta(img, ahora)
        elif self.estado == "jugando":
            self.dibujar_hud(img, t)
        elif self.estado == "pausa":
            self.dibujar_hud(img, t, cuenta=self.estado_antes_pausa == "cuenta")
            G.pegar_centro(img, G.sprite_panel(int(660 * S), int(200 * S), alpha=240), self.w // 2, self.h // 2)
            G.pegar_centro(img, G.sprite_texto("EN PAUSA", int(60 * S), G.DORADO), self.w // 2, self.h // 2 - int(35 * S))
            G.pegar_centro(img, G.sprite_texto("Pulsa P o Continuar para seguir", int(28 * S)),
                           self.w // 2, self.h // 2 + int(40 * S))
        elif self.estado == "fin":
            self.dibujar_fin(img)

        if self.estado in ("jugando", "cuenta", "pausa"):
            self.dibujar_controles(img)

        if imagen_camara is not None and self.estado != "fin":
            self.dibujar_camara(img, imagen_camara, manos if mostrar_manos else [])
        elif mostrar_manos and imagen_camara is None:
            dibujar_manos(img, manos, S)
        for c in cursores:
            dibujar_cursor(img, c.posicion, t, S, activo=c.pinza)

    def dibujar_camara(self, img, imagen, manos):
        x, y, w, h = self.rect_camara
        S = self.S
        G.pegar(img, G.sprite_panel(w, h, (16, 29, 52), 255, int(14 * S), (147, 231, 251), 3), x, y)
        G.pegar_izq(img, G.sprite_texto("Tu cámara", int(18 * S)), x + int(12 * S), y + int(16 * S))
        py, margen = y + int(32 * S), int(7 * S)
        disponible_w, disponible_h = w - 2 * margen, y + h - margen - py
        ih, iw = imagen.shape[:2]
        escala = min(disponible_w / iw, disponible_h / ih)
        vw, vh = max(1, round(iw * escala)), max(1, round(ih * escala))
        vista = cv2.resize(imagen, (vw, vh), interpolation=cv2.INTER_AREA)
        manos_pequenas = [[(round(px * vw / self.w), round(py * vh / self.h)) for px, py in mano] for mano in manos]
        dibujar_manos(vista, manos_pequenas, escala)
        vx, vy = x + (w - vw) // 2, py + (disponible_h - vh) // 2
        img[vy:vy + vh, vx:vx + vw] = vista

    def dibujar_boton(self, img, clave, rect, texto, color=(38, 62, 105), seleccionado=False):
        x, y, w, h = rect
        S = self.S
        borde = (158, 238, 243) if seleccionado else (180, 198, 226)
        G.pegar(img, G.sprite_panel(w, h, color, 255, int(13 * S), borde, max(1, int(2 * S))), x, y)
        G.pegar_centro(img, G.sprite_texto(texto, int(23 * S)), x + w // 2, y + h // 2)
        self.dibujar_progreso(img, clave, rect)

    def dibujar_progreso(self, img, clave, rect):
        prog = min(1.0, self.dwell_ui.get(clave, 0.0) / 1.2)
        if prog > 0:
            x, y, w, h = rect
            margen = int(12 * self.S)
            comienzo = (x + margen, y + h - int(7 * self.S))
            fin = (comienzo[0] + int((w - 2 * margen) * prog), comienzo[1])
            cv2.line(img, comienzo, fin, G.bgr(G.DORADO), max(2, int(4 * self.S)), cv2.LINE_AA)

    def dibujar_controles(self, img):
        for clave, rect in self.controles.items():
            texto = ("Continuar [P]" if self.estado == "pausa" else "Pausar [P]") if clave == "pausa" else "Terminar [T]"
            color = (55, 110, 210) if clave == "pausa" else (200, 65, 65)
            self.dibujar_boton(img, clave, rect, texto, color)

    def dibujar_ramo(self, img, t):
        hx, hy = self.zona
        S = self.S
        n = len(self.entregados[-7:])
        for i, color in enumerate(self.entregados[-7:]):
            ang = -math.pi / 2 + (i - (n - 1) / 2) * 0.38
            gx = hx + 62 * S * math.cos(ang) + 4 * S * math.sin(t * 2 + i)
            gy = hy - 78 * S + 62 * S * math.sin(ang)
            spr, ax, ay, ky = G.sprite_globo(COLORES[color], int(26 * S))
            cv2.line(img, (hx, hy), (int(gx), int(gy + ky - ay)), (240, 240, 240), 1, cv2.LINE_AA)
            G.pegar(img, spr, gx - ax, gy - ay)

    def dibujar_zona(self, img, t, destello):
        S = self.S
        sosteniendo = self.sostenido is not None
        color_brillo = (120, 255, 150) if destello else ((255, 230, 90) if sosteniendo else (255, 255, 255))
        G.pegar_centro(img, G.sprite_brillo(int(self.radio_zona * 1.5), color_brillo), *self.zona,
                       alpha=0.9 if (destello or sosteniendo) else 0.45)
        r = int(self.radio_zona + 6 * S * math.sin(t * 4))
        col = (120, 255, 150) if destello else ((90, 230, 255) if sosteniendo else (255, 255, 255))
        for i in range(12):                          # aro punteado que gira
            a0 = i * 30 + t * 60
            cv2.ellipse(img, self.zona, (r, r), 0, a0, a0 + 18, col, max(3, int(5 * S)), cv2.LINE_AA)
        if sosteniendo and not destello:
            G.pegar_centro(img, G.sprite_texto("¡Aquí!", int(30 * S), (255, 255, 255), 3), self.zona[0],
                           self.zona[1] + self.radio_zona + int(28 * S))

    def linea_guia(self, img, a, b, t):
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        if dist < 1:
            return
        paso = 26 * self.S
        desfase = (t * 60 * self.S) % paso
        n = int(dist / paso)
        for i in range(n):
            k = (i * paso + desfase) / dist
            if k > 1:
                break
            p = (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k))
            cv2.circle(img, p, max(3, int(5 * self.S)), (90, 230, 255), -1, cv2.LINE_AA)

    def dibujar_hud(self, img, t, cuenta=False):
        S = self.S
        # puntos
        G.pegar(img, G.sprite_panel(int(240 * S), int(78 * S)), int(18 * S), int(18 * S))
        G.pegar_centro(img, G.sprite_estrella(int(50 * S)), int(58 * S), int(57 * S))
        G.pegar_izq(img, G.sprite_texto(str(self.puntos), int(46 * S)), int(92 * S), int(57 * S))
        # modo y racha
        y = int(125 * S)
        chip = G.sprite_pildora(f"{self.modo.capitalize()} / {self.velocidad}", int(22 * S), (52, 82, 167))
        G.pegar(img, chip, int(18 * S), y - chip.shape[0] // 2)
        if self.racha >= 2:
            chip2 = G.sprite_pildora(f"Racha x{self.racha}", int(24 * S), (235, 90, 40))
            G.pegar(img, chip2, int(28 * S) + chip.shape[1], y - chip2.shape[0] // 2)
        # temporizador
        restante = self.duracion if cuenta else (self.tiempo_restante() if self.estado in ("jugando", "pausa") else 0)
        c = (self.centro_juego, int(62 * S))
        G.pegar_centro(img, G.sprite_panel(int(104 * S), int(104 * S), radio=int(52 * S)), *c)
        frac = restante / self.duracion
        col = (80, 200, 60) if restante > 20 else ((30, 200, 250) if restante > 10 else (60, 60, 240))
        arco(img, c, int(42 * S), frac, col, max(5, int(8 * S)), (90, 90, 100))
        G.pegar_centro(img, G.sprite_texto(str(int(math.ceil(restante))), int(38 * S)), *c)
        # pedido del globero
        burbuja = G.sprite_burbuja(self.modo, self.objetivo, round(S * 0.9, 2))
        bx = self.w - burbuja.shape[1] - int(8 * S)
        G.pegar(img, burbuja, bx, int(6 * S + 3 * S * math.sin(t * 2)))
        # mensaje
        if self.mensaje and time.monotonic() < self.mensaje[1]:
            G.pegar_centro(img, self.mensaje[0], self.centro_juego, self.h - int(115 * S))

    def dibujar_menu(self, img, t):
        S = self.S
        titulo = G.sprite_titulo("ATRAPA GLOBOS", int(84 * S))
        G.pegar_centro(img, titulo, self.centro_juego, int(98 * S + 4 * S * math.sin(t * 2)))
        sub = G.sprite_pildora("Junta pulgar e índice para atrapar un globo", int(24 * S), (35, 40, 60))
        G.pegar_centro(img, sub, self.centro_juego, int(170 * S))
        for modo, rect in self.tarjetas.items():
            x, y, w, h = rect
            G.pegar(img, G.sprite_tarjeta(modo, w, h, self.dwell_ui.get(modo, 0) > 0), x, y)
            self.dibujar_progreso(img, modo, rect)
        x0 = self.acceso_historial[0]
        for nombre, y in (("Velocidad", 471), ("Vista", 533), ("Nombre", 595)):
            G.pegar_izq(img, G.sprite_texto(nombre, int(24 * S), borde=2), x0, int(y * S))
        for opcion, rect in self.ajustes.items():
            activo = opcion in (self.velocidad, self.vista)
            self.dibujar_boton(img, opcion, rect, opcion, (14, 112, 119) if activo else (38, 62, 105), activo)
        self.dibujar_campo_nombre(img)
        self.dibujar_boton(img, "historial", self.acceso_historial, "Ver historial")
        ayuda = "Enter guarda / Esc cancela" if self.borrador_nombre is not None else "Elige un juego con el dedo o haz clic"
        G.pegar_izq(img, G.sprite_texto(ayuda, int(20 * S), borde=2), x0 + int(260 * S), int(666 * S))

    def dibujar_campo_nombre(self, img):
        x, y, w, h = self.campo_nombre
        S = self.S
        activo = self.borrador_nombre is not None
        borde = (158, 238, 243) if activo else (180, 198, 226)
        G.pegar(img, G.sprite_panel(w, h, (22, 37, 64), 255, int(12 * S), borde, max(1, int(2 * S))), x, y)
        tam = int(22 * S)
        nombre = self.borrador_nombre if activo else self.nombre
        texto = G.texto_recortado(nombre, tam, w - int(40 * S))
        if activo:
            texto += "|"
        color = (255, 255, 255) if texto else (181, 204, 229)
        etiqueta = G.sprite_texto(texto or "Haz clic para escribir tu nombre", tam, color, sombra=False)
        G.pegar_izq(img, etiqueta, x + int(10 * S), y + h // 2)

    def dibujar_cantidad(self, img):
        S = self.S
        cx, cy = self.centro_juego, self.h // 2
        modo = self.modo_elegido
        singular, plural = NOMBRES_OPCIONES[modo]
        panel = G.sprite_panel(int(740 * S), int(405 * S), (21, 32, 55), 248, int(26 * S), (176, 202, 235), 3)
        G.pegar_centro(img, panel, cx, cy - int(6 * S))
        titulo = G.sprite_texto(f"¿Cuánt{'os' if modo == 'COLORES' else 'as'} {plural}?", int(49 * S))
        G.pegar_centro(img, titulo, cx, cy - int(149 * S))
        ayuda = G.sprite_texto("Elige con el dedo, el ratón o el número", int(22 * S), (182, 212, 240))
        G.pegar_centro(img, ayuda, cx, cy - int(93 * S))

        for n, rect in self.tarjetas_cantidad.items():
            x, y, w, h = rect
            borde = (158, 238, 243) if self.dwell_ui.get(n, 0) > 0 else (180, 198, 226)
            tarjeta = G.sprite_panel(w, h, (38, 62, 105), 255, int(16 * S), borde, 2)
            G.pegar(img, tarjeta, x, y)
            texto = G.sprite_texto(f"{n} {singular if n == 1 else plural}", int(27 * S))
            G.pegar_centro(img, texto, x + w // 2, y + int(36 * S))
            for i, opcion in enumerate(OPCIONES[modo][:n]):
                px = x + w // 2 + (i - (n - 1) / 2) * int(48 * S)
                py = y + int(93 * S)
                if modo == "COLORES":
                    globo, ax, ay, _ = G.sprite_globo(COLORES[opcion], int(20 * S))
                    G.pegar(img, globo, px - ax, py - ay)
                else:
                    sprite = (G.sprite_forma(opcion, int(45 * S), COLORES["AZUL"]) if modo == "FORMAS"
                              else G.sprite_texto(opcion, int(42 * S), (196, 225, 255)))
                    G.pegar_centro(img, sprite, px, py)
            self.dibujar_progreso(img, n, rect)
        self.dibujar_boton(img, "menu", self.volver_cantidad, "Volver al menú")

    def dibujar_cuenta(self, img, ahora):
        transcurrido = ahora - self.t_cuenta
        numero = 3 - int(transcurrido / 0.8)
        fase = (transcurrido % 0.8) / 0.8
        texto = str(numero) if numero > 0 else "¡YA!"
        tam = int((170 if numero > 0 else 150) * self.S * (1.25 - 0.25 * min(1, fase * 3)))
        spr = G.sprite_texto(texto, tam, (255, 255, 255), max(4, tam // 14), (235, 60, 60) if numero > 0 else (40, 170, 80))
        G.pegar_centro(img, spr, self.centro_juego, self.h // 2, alpha=1.0 if numero > 0 else 1 - fase * 0.5)

    def dibujar_fin(self, img):
        S = self.S
        cx, cy = self.w // 2, self.h // 2
        pw, ph = int(640 * S), int(520 * S)
        G.pegar_centro(img, G.sprite_panel(pw, ph, (20, 24, 45), 225, int(36 * S), (255, 255, 255), 3), cx, cy)
        total = self.aciertos + self.errores
        precision = 100 * self.aciertos / total if total else 0
        estrellas = 3 if (self.aciertos >= 12 and precision >= 80) else (2 if self.aciertos >= 6 else (1 if self.aciertos else 0))
        titulo = ["¡Buen intento!", "¡Bien hecho!", "¡Muy bien!", "¡Excelente!"][estrellas]
        G.pegar_centro(img, G.sprite_texto(titulo, int(60 * S), G.DORADO, 4), cx, cy - int(200 * S))
        for i in range(3):
            G.pegar_centro(img, G.sprite_estrella(int((90 if i == 1 else 74) * S), i < estrellas),
                           cx + (i - 1) * int(100 * S), cy - int((110 if i == 1 else 100) * S))
        lineas = [f"Puntos: {self.puntos}", f"Globos entregados: {self.aciertos}",
                  f"Precisión: {precision:.0f}%   /   Mejor racha: {self.mejor_racha}"]
        for i, l in enumerate(lineas):
            G.pegar_centro(img, G.sprite_texto(l, int((38 if i == 0 else 28) * S)), cx, cy + int((-20 + i * 48) * S))
        etiquetas = {"otra": "Jugar otra vez", "historial": "Historial", "menu": "Menú"}
        for clave, rect in self.botones.items():
            self.dibujar_boton(img, clave, rect, etiquetas[clave], (26, 130, 94) if clave == "otra" else (38, 62, 105))

    def dibujar_historial(self, img):
        S = self.S
        cx, cy = self.w // 2, self.h // 2
        ancho, alto = int(1080 * S), int(600 * S)
        x0, y0 = cx - ancho // 2, cy - alto // 2
        panel = G.sprite_panel(ancho, alto, (21, 32, 55), 255, int(24 * S), (176, 202, 235), 3)
        G.pegar(img, panel, x0, y0)
        G.pegar_centro(img, G.sprite_texto("Historial de puntuaciones", int(40 * S)), cx, y0 + int(58 * S))
        if self.historial.partidas:
            columnas = (47, 345, 554, 697, 841, 942)
            encabezados = ("Nombre", "Fecha y hora", "Categoría", "Velocidad", "Puntos", "Aciertos")
            inicio = len(self.historial.partidas) - self.pagina_historial * FILAS_HISTORIAL
            filas = reversed(self.historial.partidas[max(0, inicio - FILAS_HISTORIAL):inicio])
            for x, texto in zip(columnas, encabezados):
                sprite = G.sprite_texto(texto, int(18 * S), (172, 223, 248))
                G.pegar_izq(img, sprite, x0 + int(x * S), y0 + int(118 * S))
            for i, fila in enumerate(filas):
                y = y0 + int((143 + i * 46) * S)
                fondo = (35, 51, 81) if i % 2 == 0 else (28, 43, 71)
                G.pegar(img, G.sprite_panel(ancho - int(66 * S), int(39 * S), fondo, 255, int(6 * S)),
                        x0 + int(33 * S), y)
                nombre = G.texto_recortado(fila.nombre, int(21 * S), int(276 * S))
                campos = (nombre, fila.fecha, fila.categoria, fila.velocidad, str(fila.puntos), str(fila.aciertos))
                for x, texto in zip(columnas, campos):
                    G.pegar_izq(img, G.sprite_texto(texto, int(21 * S)), x0 + int(x * S), y + int(20 * S))
        else:
            G.pegar_centro(img, G.sprite_texto("Aquí aparecerá tu primera partida", int(28 * S)), cx, cy)
        if self.historial.error:
            G.pegar_centro(img, G.sprite_texto(self.historial.error, int(18 * S), G.DORADO), cx, y0 + int(478 * S))
        pagina = f"Página {self.pagina_historial + 1} de {self.paginas_historial()}"
        G.pegar_centro(img, G.sprite_texto(pagina, int(20 * S)), cx - int(75 * S), cy + int(246 * S))
        for clave, rect in self.botones_visibles().items():
            self.dibujar_boton(img, clave, rect, clave.capitalize())


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------
def crear_vineta(w, h):
    """Oscurece solo las orillas: el centro (donde estás tú) queda a todo color."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    m = 1 - 0.35 * np.clip((r - 0.75) / 0.7, 0, 1) ** 1.5
    return cv2.merge([(m * 255).astype(np.uint8)] * 3)


def crear_fondo(w, h):
    """Carga el parque a pantalla completa y suaviza el contraste del fondo."""
    horizontal = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    vertical = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    mezcla = 0.7 * vertical + 0.3 * horizontal
    arriba, abajo = np.array([70, 44, 28]), np.array([101, 57, 42])  # BGR
    base = (arriba + mezcla[..., None] * (abajo - arriba)).astype(np.uint8)
    try:
        datos = np.frombuffer(FONDO_PARQUE.read_bytes(), dtype=np.uint8)
        parque = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    except (OSError, cv2.error):
        return base
    if parque is None:
        return base

    alto, ancho = parque.shape[:2]
    escala = max(w / ancho, h / alto)
    tamanio = (math.ceil(ancho * escala), math.ceil(alto * escala))
    parque = cv2.resize(parque, tamanio, interpolation=cv2.INTER_AREA if escala < 1 else cv2.INTER_LINEAR)
    x, y = (tamanio[0] - w) // 2, (tamanio[1] - h) // 2
    return cv2.addWeighted(parque[y:y + h, x:x + w], 0.80, base, 0.20, 0)


def imagen_para_detector(frame):
    """Usa el fotograma original de la cámara sin agrandarlo para MediaPipe."""
    h, w = frame.shape[:2]
    if max(w, h) > LADO_MAX_DETECCION:
        escala = LADO_MAX_DETECCION / max(w, h)
        frame = cv2.resize(frame, (max(1, round(w * escala)), max(1, round(h * escala))), interpolation=cv2.INTER_LINEAR)
    return U.a_imagen_mp(frame)


def main():
    parser = argparse.ArgumentParser(description="Atrapa globos y llévalos al globero")
    parser.add_argument("--camara", type=int, default=0)
    parser.add_argument("--tiempo", type=int, default=90, help="duración de la partida en segundos")
    parser.add_argument("--dwell", type=float, default=0.4, help="opción antigua; ahora se agarra cerrando la pinza")
    parser.add_argument("--globos", type=int, help="total de globos en pantalla; por defecto, uno por opción elegida")
    parser.add_argument("--control", choices=["mano", "cuerpo"], default="mano",
                        help="mano: índice y pinza; cuerpo: muñecas con MediaPipe Pose y agarre con pinza")
    parser.add_argument("--sin-sonido", action="store_true")
    args = parser.parse_args()
    if args.tiempo <= 0 or (args.globos is not None and args.globos <= 0):
        parser.error("--tiempo y --globos deben ser mayores que cero")

    cap = U.abrir_camara(args.camara)
    # Hand Landmarker detecta el pulgar y el índice para calcular la pinza.
    detector_manos = mp.tasks.vision.HandLandmarker.create_from_options(U.opciones_manos())
    detector_pose = None
    if args.control == "cuerpo":
        # Pose Landmarker sigue las muñecas para mover los cursores con los brazos.
        detector_pose = mp.tasks.vision.PoseLandmarker.create_from_options(U.opciones_pose())
        print("Control cuerpo: MediaPipe Pose sigue las muñecas y MediaPipe Hands detecta la pinza.")
    pinzas_previas = {}
    reloj = U.MarcaTiempo()

    ok, frame = cap.read()
    if not ok:
        raise SystemExit("No llegó imagen de la cámara.")
    fh, fw = frame.shape[:2]
    w, h = ANCHO_LIENZO, int(round(fh * ANCHO_LIENZO / fw))
    vineta = crear_vineta(w, h)
    fondo = crear_fondo(w, h)

    print("Preparando gráficos...")
    archivo_historial = Path(__file__).resolve().with_name("historial_puntuaciones.jsonl")
    juego = Juego(w, h, args.tiempo, args.globos, Sonido(not args.sin_sonido), archivo_historial)

    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, w, h)
    pantalla_completa = False
    mostrar_manos = True
    clics = []

    def al_raton(evento, x, y, flags, datos):
        if evento == cv2.EVENT_LBUTTONUP:
            clics.append((x, y))

    cv2.setMouseCallback(VENTANA, al_raton)
    print("Listo: abre pulgar e índice y júntalos sobre un globo para agarrarlo.")
    print("Mantén la pinza para llevarlo; abre los dedos para soltarlo.")
    print("P/ESPACIO: pausar o continuar | T: terminar partida | Q/ESC: salir")

    t0 = prev = time.monotonic()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)                       # efecto espejo: te ves como en un espejo
        ahora = time.monotonic()
        dt, prev = min(ahora - prev, 0.1), ahora
        t = ahora - t0

        imagen, marca = imagen_para_detector(frame), reloj.ms()
        res_manos = detector_manos.detect_for_video(imagen, marca)
        if detector_pose is None:
            cursores, manos = leer_cursores(res_manos, w, h, args.control, pinzas_previas)
        else:
            res_pose = detector_pose.detect_for_video(imagen, marca)
            cursores, manos = leer_cursores(res_pose, w, h, args.control, pinzas_previas, res_manos)
        for x, y in clics:
            juego.clic(x, y)
        clics.clear()
        juego.actualizar(cursores, dt, t)
        usar_fondo = juego.vista == "Fondo"
        if usar_fondo:
            lienzo = fondo.copy()
        else:
            vista = frame if frame.shape[:2] == (h, w) else cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
            lienzo = cv2.multiply(vista, vineta, scale=1 / 255)
        juego.dibujar(lienzo, cursores, manos, t, dt, mostrar_manos, imagen_camara=frame if usar_fondo else None)
        cv2.imshow(VENTANA, lienzo)

        tecla = cv2.waitKeyEx(1)
        if juego.escribir_nombre(tecla):
            continue
        tecla &= 0xFF
        if tecla == 27 and juego.estado == "cantidad":
            juego.activar_boton("menu")
        elif tecla in (ord("q"), 27):
            break
        elif tecla in (ord("p"), ord(" ")) and juego.estado in ("jugando", "cuenta", "pausa"):
            juego.alternar_pausa()
        elif tecla == ord("t") and juego.estado in ("jugando", "cuenta", "pausa"):
            juego.terminar()
        elif tecla in (ord("1"), ord("2"), ord("3")):
            numero = int(chr(tecla))
            if juego.estado == "cantidad":
                if numero in juego.cantidades:
                    juego.activar_boton(numero)
            else:
                juego.activar_boton(MODOS[numero])
        elif tecla == ord(" ") and juego.estado == "menu":
            juego.activar_boton(juego.modo)
        elif tecla == ord(" ") and juego.estado == "fin":
            juego.iniciar_cuenta(juego.modo)
        elif tecla == ord("r") and juego.estado != "cantidad":
            juego.iniciar_cuenta(juego.modo)
        elif tecla == ord("m"):
            juego.ir_menu()
        elif tecla == ord("h"):
            mostrar_manos = not mostrar_manos
        elif tecla == ord("f"):
            pantalla_completa = not pantalla_completa
            cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if pantalla_completa else cv2.WINDOW_NORMAL)

    detector_manos.close()
    if detector_pose is not None:
        detector_pose.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
