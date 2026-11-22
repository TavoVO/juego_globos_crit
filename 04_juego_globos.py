"""
PASO 4 - JUEGO: Atrapa globos y llévalos a la mano del globero.

Cómo se juega
-------------
1. En el menú, pon el dedo sobre una tarjeta (Colores, Formas o Letras)
   hasta que se llene la barra. Empieza una cuenta regresiva 3, 2, 1.
2. Abre el pulgar y el índice, apunta a un globo y júntalos para atraparlo.
3. Mantén la pinza cerrada y llévalo al globero. Abre los dedos para soltarlo.
4. El globero pide un globo en su burbuja. Si entregas el correcto ganas
   puntos y confeti; si no, el globo se revienta y te recuerda cuál buscar
   (sin restar puntos).

Te ves a ti mismo a color en la pantalla (efecto espejo) y el contorno de tu
mano se dibuja encima, para que sepas exactamente dónde estás.

Ejecutar:  python 04_juego_globos.py
Opciones:  --tiempo 90   --globos 5   --control mano|cuerpo   --sin-sonido
Teclas:    1/2/3 = jugar ese modo   ESPACIO = empezar   M = menú   R = reiniciar
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
import numpy as np

import graficos as G
import utilidades as U

VENTANA = "Atrapa Globos - CRIT"
ANCHO_LIENZO = 1280

COLORES = G.COLORES_GLOBO
FORMAS = ["CIRCULO", "CUADRADO", "TRIANGULO", "ESTRELLA"]
LETRAS = list("AEIOUMPS")
MODOS = {1: "COLORES", 2: "FORMAS", 3: "LETRAS"}
CAMPO = {"COLORES": "color", "FORMAS": "forma", "LETRAS": "letra"}
OPCIONES = {"COLORES": list(COLORES), "FORMAS": FORMAS, "LETRAS": LETRAS}

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
    def __init__(self, x_min, x_max, alto, escala):
        self.x_min, self.x_max, self.alto, self.S = x_min, x_max, alto, escala
        self.reiniciar(primera_vez=True)

    def reiniciar(self, forzar=None, primera_vez=False):
        self.r = int(random.randint(46, 58) * self.S)
        self.x = random.uniform(self.x_min + self.r, self.x_max - self.r)
        if primera_vez:   # al empezar, algunos globos ya están en pantalla
            self.y = random.uniform(self.alto * 0.35, self.alto * 1.4)
        else:
            self.y = self.alto + self.r * 1.5 + random.uniform(0, self.alto * 0.4)
        self.vy = random.uniform(45, 80) * self.S
        self.fase = random.uniform(0, 2 * math.pi)
        self.x_osc = 0.0
        self.color = random.choice(list(COLORES))
        self.forma = random.choice(FORMAS)
        self.letra = random.choice(LETRAS)
        if forzar:
            setattr(self, forzar[0], forzar[1])
        self.agarrado = False

    def atributo(self, modo):
        return getattr(self, CAMPO[modo])

    def actualizar(self, dt, t):
        if not self.agarrado:
            self.y -= self.vy * dt
            self.x_osc = 14 * self.S * math.sin(t * 1.4 + self.fase)
            if self.y < -self.r * 1.5:              # se escapó por arriba
                self.reiniciar()

    def centro(self):
        return int(self.x + (0 if self.agarrado else self.x_osc)), int(self.y)

    def contiene(self, p):
        cx, cy = self.centro()
        return math.hypot(p[0] - cx, p[1] - cy) < self.r * 1.25

    def visible(self):
        return -self.r < self.y < self.alto - self.r * 0.5

    def dibujar(self, img, modo, t):
        tipo = modo if modo in ("FORMAS", "LETRAS") else None
        simbolo = {"FORMAS": self.forma, "LETRAS": self.letra}.get(modo)
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


def leer_cursores(res, w, h, control, pinzas_previas, res_manos=None):
    """Pinza relativa al tamaño de la palma, con histéresis para evitar temblores."""
    cursores, manos = [], []
    resultado_manos = res if control == "mano" else res_manos
    estados = {}
    if resultado_manos is not None:
        for i, mano in enumerate(resultado_manos.hand_landmarks):
            pts = [(int(p.x * w), int(p.y * h)) for p in mano]
            manos.append(pts)
            etiquetas = resultado_manos.handedness[i]
            identidad = etiquetas[0].category_name if etiquetas else f"mano-{i}"
            if identidad in estados:
                identidad = f"{identidad}-{i}"
            palma = max(math.dist(pts[0], pts[9]), math.dist(pts[5], pts[17]), 1)
            umbral = 0.48 if pinzas_previas.get(identidad, False) else 0.32
            pinza = math.dist(pts[4], pts[8]) / palma < umbral
            estados[identidad] = pinza
            # El punto de pinza queda entre las dos yemas.
            posicion = tuple((a + b) // 2 for a, b in zip(pts[4], pts[8])) if pinza else pts[8]
            cursores.append(Cursor(posicion, identidad, pinza))
    pinzas_previas.clear()
    pinzas_previas.update(estados)
    if control == "cuerpo":
        manos_cursores, cursores = cursores, []
        for cuerpo in res.pose_landmarks:
            for idx in (15, 16):
                p = cuerpo[idx]
                vis = p.visibility if p.visibility is not None else 1.0
                if vis > 0.5:
                    posicion = (int(p.x * w), int(p.y * h))
                    cercanas = [(math.dist(pts[0], posicion), c) for pts, c in zip(manos, manos_cursores)]
                    distancia, mano = min(cercanas, key=lambda par: par[0]) if cercanas else (math.inf, None)
                    cerrada = distancia < math.hypot(w, h) * 0.15 and mano.pinza
                    cursores.append(Cursor(posicion, f"muneca-{idx}", cerrada))
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
    def __init__(self, w, h, duracion, n_globos, sonido):
        self.w, self.h = w, h
        self.S = S = min(h / 720, w / 1280)   # escala para cualquier resolución
        self.duracion, self.n_globos = duracion, n_globos
        self.sonido = sonido
        self.efectos = Efectos(S)

        self.spr_globero, mx, my = G.sprite_globero(int(460 * S))
        gh, gw = self.spr_globero.shape[:2]
        self.pos_globero = (w - gw - int(15 * S), h - gh)
        self.zona = (self.pos_globero[0] + int(mx), self.pos_globero[1] + int(my))
        self.radio_zona = int(72 * S)
        self.x_max_globos = self.zona[0] - self.radio_zona - int(30 * S)
        self.centro_juego = self.x_max_globos // 2 + int(20 * S)

        # tarjetas del menú
        tw, th, sep = int(230 * S), int(200 * S), int(26 * S)
        x0 = self.centro_juego - (3 * tw + 2 * sep) // 2
        self.tarjetas = {MODOS[i + 1]: (x0 + i * (tw + sep), int(330 * S), tw, th) for i in range(3)}
        # botones de la pantalla final
        bw, bh = int(285 * S), int(80 * S)
        cy = int(h * 0.5 + 175 * S)
        self.botones = {"otra": (w // 2 - bw - int(15 * S), cy, bw, bh, "Jugar otra vez", (40, 170, 80)),
                        "menu": (w // 2 + int(15 * S), cy, bw, bh, "Menú", (70, 110, 240))}
        self.controles = {
            "pausa": (int(18 * S), h - int(64 * S), int(220 * S), int(48 * S)),
            "terminar": (int(252 * S), h - int(64 * S), int(220 * S), int(48 * S)),
        }
        self.pinzas_listas = set()
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
        self.globos = [Globo(int(30 * self.S), self.x_max_globos, self.h, self.S) for _ in range(self.n_globos)]
        self.sostenido = None
        self.dueno_globo = None
        self.perdido = 0.0
        self.mensaje = None
        self.destello_hasta = 0.0
        self.dwell_ui = {}
        self.bloqueo_controles = False
        self.nuevo_objetivo()

    def iniciar_cuenta(self, modo):
        self.preparar_partida(modo)
        self.estado = "cuenta"
        self.t_cuenta = time.monotonic()
        self.ultimo_numero = None

    def empezar(self):
        self.estado = "jugando"
        self.inicio = time.monotonic()

    def terminar(self):
        self.estado = "fin"
        self.dwell_ui = {}
        if self.sostenido:
            self.sostenido.agarrado = False
            self.sostenido = None
        self.dueno_globo = None
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

    def clic(self, x, y):
        if self.estado not in ("jugando", "cuenta", "pausa"):
            return
        for clave, (bx, by, bw, bh) in self.controles.items():
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.alternar_pausa() if clave == "pausa" else self.terminar()
                return

    def sobre_controles(self, posicion):
        return any(x <= posicion[0] <= x + w and y <= posicion[1] <= y + h
                   for x, y, w, h in self.controles.values())

    # --- lógica -------------------------------------------------------------
    def nuevo_objetivo(self):
        visibles = [g.atributo(self.modo) for g in self.globos if g.visible() and not g.agarrado]
        self.objetivo = random.choice(visibles or OPCIONES[self.modo])
        self.asegurar_objetivo()

    def asegurar_objetivo(self):
        """Garantiza que siempre exista al menos un globo correcto."""
        if any(g.atributo(self.modo) == self.objetivo for g in self.globos):
            return
        libres = [g for g in self.globos if not g.agarrado]
        max(libres, key=lambda g: g.y).reiniciar(forzar=(CAMPO[self.modo], self.objetivo))

    def avisar(self, texto, color, segundos=1.4):
        self.mensaje = (G.sprite_pildora(texto, int(34 * self.S), color), time.monotonic() + segundos)

    def tiempo_restante(self):
        ahora = self.t_pausa if self.estado == "pausa" else time.monotonic()
        return max(0.0, self.duracion - (ahora - self.inicio))

    def hover(self, clave, rect, cursores, dt, segundos=1.2):
        """Botón que se activa dejando el dedo encima. Regresa (progreso, activado)."""
        x, y, w, h = rect[:4]
        dentro = any(x < c.posicion[0] < x + w and y < c.posicion[1] < y + h for c in cursores)
        p = self.dwell_ui.get(clave, 0.0)
        p = p + dt if dentro else max(0.0, p - 2 * dt)
        self.dwell_ui[clave] = p
        if p >= segundos:
            self.dwell_ui = {}
            return 1.0, True
        return p / segundos, False

    def actualizar(self, cursores, dt, t):
        ahora = time.monotonic()
        presentes = {c.identidad for c in cursores}
        self.pinzas_listas.intersection_update(presentes)
        nuevas_pinzas = []
        for c in cursores:
            if not c.pinza:
                self.pinzas_listas.add(c.identidad)
            elif c.identidad in self.pinzas_listas:
                nuevas_pinzas.append(c)
                self.pinzas_listas.discard(c.identidad)

        if self.estado in ("jugando", "cuenta", "pausa"):
            sobre_control = any(self.sobre_controles(c.posicion) for c in cursores)
            if self.bloqueo_controles:
                if not sobre_control:
                    self.bloqueo_controles = False
            else:
                for clave, rect in self.controles.items():
                    _, listo = self.hover(clave, rect, cursores, dt)
                    if listo:
                        self.alternar_pausa() if clave == "pausa" else self.terminar()
                        return
        if self.estado == "pausa":
            return
        self.t_animacion += dt
        t = self.t_animacion
        if self.estado in ("menu", "cuenta", "fin"):
            for g in self.globos:
                g.actualizar(dt, t)

        if self.estado == "menu":
            for modo, rect in self.tarjetas.items():
                _, listo = self.hover(modo, rect, cursores, dt)
                if listo:
                    self.iniciar_cuenta(modo)
                    return
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

        if self.estado == "fin":
            for clave, rect in self.botones.items():
                _, listo = self.hover(clave, rect, cursores, dt)
                if listo:
                    self.iniciar_cuenta(self.modo) if clave == "otra" else self.ir_menu()
                    return
            return

        # --- jugando ---
        if self.tiempo_restante() <= 0:
            self.terminar()
            return
        for g in self.globos:
            g.actualizar(dt, t)
        self.asegurar_objetivo()

        if self.sostenido is None:
            for c in nuevas_pinzas:
                if self.sobre_controles(c.posicion):
                    continue
                for g in reversed(self.globos):
                    if g.contiene(c.posicion):
                        g.agarrado, self.sostenido, self.perdido = True, g, 0.0
                        self.dueno_globo = c.identidad
                        self.sonido("agarrar")
                        return
            return

        g = self.sostenido
        propietario = next((c for c in cursores if c.identidad == self.dueno_globo), None)
        if propietario is None:
            self.perdido += dt
            if self.perdido > 1.0:                  # se perdió la mano: soltar el globo
                self.soltar()
            return
        self.perdido = 0.0
        if not propietario.pinza:
            self.soltar()
            return
        cx, cy = propietario.posicion
        k = min(1.0, dt * 15)                       # suavizado
        g.x += (cx - g.x) * k
        g.y += (cy - g.r * 0.9 - g.y) * k           # el globo queda justo arriba del dedo
        if math.hypot(cx - self.zona[0], cy - self.zona[1]) < self.radio_zona + 15 * self.S:
            self.entregar(g, ahora)

    def soltar(self):
        if self.sostenido is not None:
            self.sostenido.agarrado = False
        self.sostenido = None
        self.dueno_globo = None
        self.perdido = 0.0

    def entregar(self, g, ahora):
        self.sostenido = None
        self.dueno_globo = None
        x, y = g.centro()
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
    def dibujar(self, img, cursores, manos, t, dt, mostrar_manos):
        S = self.S
        t = self.t_animacion
        ahora = self.t_pausa if self.estado == "pausa" else time.monotonic()

        self.dibujar_ramo(img, t)
        G.pegar(img, self.spr_globero, *self.pos_globero)
        if self.estado in ("jugando", "cuenta", "pausa"):
            self.dibujar_zona(img, t, ahora < self.destello_hasta)

        modo_globo = self.modo if self.estado != "menu" else "COLORES"
        for g in self.globos:
            if g is not self.sostenido:
                g.dibujar(img, modo_globo, t)
        if self.sostenido is not None:
            g = self.sostenido
            c = g.centro()
            self.linea_guia(img, (c[0], c[1] + g.r), self.zona, t)
            G.pegar_centro(img, G.sprite_brillo(int(g.r * 1.7), (255, 240, 140)), *c, alpha=0.9)
            g.dibujar(img, modo_globo, t)

        self.efectos.actualizar_y_dibujar(img, 0 if self.estado == "pausa" else dt, ahora)

        if self.estado == "menu":
            self.dibujar_menu(img, t)
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

        if mostrar_manos:
            dibujar_manos(img, manos, S)
        for c in cursores:
            dibujar_cursor(img, c.posicion, t, S, activo=c.pinza)

    def dibujar_controles(self, img):
        S = self.S
        for clave, (x, y, w, h) in self.controles.items():
            texto = ("Continuar [P]" if self.estado == "pausa" else "Pausar [P]") if clave == "pausa" else "Terminar [T]"
            color = (55, 110, 210) if clave == "pausa" else (200, 65, 65)
            G.pegar(img, G.sprite_panel(w, h, color, 240, int(14 * S), (255, 255, 255), 2), x, y)
            G.pegar_centro(img, G.sprite_texto(texto, int(24 * S)), x + w // 2, y + h // 2)
            progreso = min(1.0, self.dwell_ui.get(clave, 0.0) / 1.2)
            if progreso > 0:
                cv2.line(img, (x + 10, y + h - 5), (x + 10 + int((w - 20) * progreso), y + h - 5),
                         (255, 255, 255), max(2, int(4 * S)), cv2.LINE_AA)

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
        chip = G.sprite_pildora(self.modo.capitalize(), int(24 * S), (70, 110, 240))
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
        burbuja = G.sprite_burbuja(self.modo, self.objetivo, round(S, 2))
        bx = self.w - burbuja.shape[1] - int(8 * S)
        G.pegar(img, burbuja, bx, int(6 * S + 3 * S * math.sin(t * 2)))
        # mensaje
        if self.mensaje and time.monotonic() < self.mensaje[1]:
            G.pegar_centro(img, self.mensaje[0], self.centro_juego, self.h - int(115 * S))

    def dibujar_menu(self, img, t):
        S = self.S
        titulo = G.sprite_titulo("ATRAPA GLOBOS", int(92 * S))
        G.pegar_centro(img, titulo, self.centro_juego, int(120 * S + 6 * S * math.sin(t * 2)))
        sub = G.sprite_pildora("Junta pulgar e índice para agarrar un globo", int(27 * S), (35, 40, 60))
        G.pegar_centro(img, sub, self.centro_juego, int(250 * S))
        for modo, (x, y, w, h) in self.tarjetas.items():
            prog = self.dwell_ui.get(modo, 0.0) / 1.2
            G.pegar(img, G.sprite_tarjeta(modo, w, h, prog > 0), x, y)
            if prog > 0:
                bx0, bx1, by = x + int(20 * S), x + w - int(20 * S), y + h - int(16 * S)
                cv2.line(img, (bx0, by), (bx1, by), (200, 200, 200), max(6, int(10 * S)), cv2.LINE_AA)
                cv2.line(img, (bx0, by), (int(bx0 + (bx1 - bx0) * prog), by), G.bgr(G.DORADO),
                         max(6, int(10 * S)), cv2.LINE_AA)
        txt = G.sprite_pildora("Pon tu dedo sobre un juego para empezar", int(26 * S), (40, 170, 80))
        G.pegar_centro(img, txt, self.centro_juego, int(600 * S))

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
                  f"Precisión: {precision:.0f}%   ·   Mejor racha: {self.mejor_racha}"]
        for i, l in enumerate(lineas):
            G.pegar_centro(img, G.sprite_texto(l, int((38 if i == 0 else 28) * S)), cx, cy + int((-20 + i * 48) * S))
        for clave, (x, y, w, h, texto, color) in self.botones.items():
            G.pegar(img, G.sprite_panel(w, h, color, 240, h // 2, (255, 255, 255), 3), x, y)
            G.pegar_centro(img, G.sprite_texto(texto, int(28 * S)), x + w // 2, y + h // 2)
            prog = self.dwell_ui.get(clave, 0.0) / 1.2
            if prog > 0:
                cv2.line(img, (x + h // 2, y + h - int(10 * S)), (int(x + h // 2 + (w - h) * prog), y + h - int(10 * S)),
                         (255, 255, 255), max(4, int(6 * S)), cv2.LINE_AA)


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------
def crear_vineta(w, h):
    """Oscurece solo las orillas: el centro (donde estás tú) queda a todo color."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    m = 1 - 0.35 * np.clip((r - 0.75) / 0.7, 0, 1) ** 1.5
    return cv2.merge([(m * 255).astype(np.uint8)] * 3)


def main():
    parser = argparse.ArgumentParser(description="Atrapa globos y llévalos al globero")
    parser.add_argument("--camara", type=int, default=0)
    parser.add_argument("--tiempo", type=int, default=90, help="duración de la partida en segundos")
    parser.add_argument("--dwell", type=float, default=0.4, help="opción antigua; ahora se agarra cerrando la pinza")
    parser.add_argument("--globos", type=int, default=5, help="globos en pantalla")
    parser.add_argument("--control", choices=["mano", "cuerpo"], default="mano")
    parser.add_argument("--sin-sonido", action="store_true")
    args = parser.parse_args()
    if args.tiempo <= 0 or args.globos <= 0:
        parser.error("--tiempo y --globos deben ser mayores que cero")

    cap = U.abrir_camara(args.camara)
    detector = U.crear_detector_manos(2) if args.control == "mano" else U.crear_detector_pose()
    detector_manos = U.crear_detector_manos(2) if args.control == "cuerpo" else None
    pinzas_previas = {}
    reloj = U.MarcaTiempo()

    ok, frame = cap.read()
    if not ok:
        raise SystemExit("No llegó imagen de la cámara.")
    fh, fw = frame.shape[:2]
    w, h = ANCHO_LIENZO, int(round(fh * ANCHO_LIENZO / fw))
    vineta = crear_vineta(w, h)

    print("Preparando gráficos...")
    juego = Juego(w, h, args.tiempo, args.globos, Sonido(not args.sin_sonido))

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
        if frame.shape[1] != w:
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
        ahora = time.monotonic()
        dt, prev = min(ahora - prev, 0.1), ahora
        t = ahora - t0

        imagen, marca = U.a_imagen_mp(frame), reloj.ms()
        res = detector.detect_for_video(imagen, marca)
        res_manos = detector_manos.detect_for_video(imagen, marca) if detector_manos else None
        cursores, manos = leer_cursores(res, w, h, args.control, pinzas_previas, res_manos)
        frame = cv2.multiply(frame, vineta, scale=1 / 255)

        for x, y in clics:
            juego.clic(x, y)
        clics.clear()
        juego.actualizar(cursores, dt, t)
        juego.dibujar(frame, cursores, manos, t, dt, mostrar_manos)
        cv2.imshow(VENTANA, frame)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27):
            break
        elif tecla in (ord("p"), ord(" ")) and juego.estado in ("jugando", "cuenta", "pausa"):
            juego.alternar_pausa()
        elif tecla == ord("t") and juego.estado in ("jugando", "cuenta", "pausa"):
            juego.terminar()
        elif tecla in (ord("1"), ord("2"), ord("3")):
            juego.iniciar_cuenta(MODOS[int(chr(tecla))])
        elif tecla == ord(" ") and juego.estado in ("menu", "fin"):
            juego.iniciar_cuenta(juego.modo)
        elif tecla == ord("r"):
            juego.iniciar_cuenta(juego.modo)
        elif tecla == ord("m"):
            juego.ir_menu()
        elif tecla == ord("h"):
            mostrar_manos = not mostrar_manos
        elif tecla == ord("f"):
            pantalla_completa = not pantalla_completa
            cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if pantalla_completa else cv2.WINDOW_NORMAL)

    detector.close()
    if detector_manos:
        detector_manos.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
