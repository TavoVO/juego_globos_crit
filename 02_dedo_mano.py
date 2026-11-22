"""
PASO 2 - MediaPipe Hands: detectar el dedo índice y "pintar en el aire".

- Solo el índice levantado  -> pinta
- Índice + medio levantados -> mueve sin pintar
- Mano abierta (5 dedos) 1 segundo -> borra todo
- Pasa el dedo sobre un cuadro de color de arriba para cambiar de color
  (componente cognitivo: reconocer y nombrar colores)

Ejecutar:  python 02_dedo_mano.py
Teclas:    C = borrar   |   Q o ESC = salir
"""
import argparse
import math
import time

import cv2
import numpy as np

import utilidades as U

PALETA = [
    ("ROJO", (40, 40, 230)),
    ("AZUL", (230, 120, 30)),
    ("VERDE", (60, 190, 60)),
    ("AMARILLO", (30, 220, 240)),
]


def dedos_levantados(p):
    """p: 21 puntos (x, y) en píxeles. Regresa [pulgar, indice, medio, anular, menique]."""
    def dist(a, b):
        return math.hypot(p[a][0] - p[b][0], p[a][1] - p[b][1])

    pulgar = dist(4, 17) > dist(3, 17)          # funciona para mano izquierda y derecha
    otros = [p[t][1] < p[t - 2][1] for t in (8, 12, 16, 20)]  # punta arriba de la articulación
    return [pulgar] + otros


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camara", type=int, default=0)
    args = parser.parse_args()

    cap = U.abrir_camara(args.camara)
    detector = U.crear_detector_manos(num_manos=1)
    reloj = U.MarcaTiempo()

    ok, frame = cap.read()
    if not ok:
        raise SystemExit("No llegó imagen de la cámara.")
    h, w = frame.shape[:2]
    lienzo = np.zeros_like(frame)
    color_nombre, color = PALETA[0]
    anterior = None
    mano_abierta_desde = None

    ancho_caja = 160
    cajas = [((20 + i * (ancho_caja + 15), 15), (20 + i * (ancho_caja + 15) + ancho_caja, 85)) for i in range(len(PALETA))]

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        res = detector.detect_for_video(U.a_imagen_mp(frame), reloj.ms())

        num_dedos = 0
        if res.hand_landmarks:
            pts = U.dibujar_mano(frame, res.hand_landmarks[0])
            dedos = dedos_levantados(pts)
            num_dedos = sum(dedos)
            punta = pts[8]

            # ¿El dedo está sobre un cuadro de color?
            for (nombre, c), ((x1, y1), (x2, y2)) in zip(PALETA, cajas):
                if x1 < punta[0] < x2 and y1 < punta[1] < y2:
                    color_nombre, color = nombre, c

            if dedos[1] and not any(dedos[2:]):           # solo índice -> pintar
                if anterior is not None:
                    cv2.line(lienzo, anterior, punta, color, 12, cv2.LINE_AA)
                anterior = punta
                cv2.circle(frame, punta, 12, color, -1)
            else:
                anterior = None
                cv2.circle(frame, punta, 12, color, 3)

            if num_dedos == 5:                              # mano abierta -> borrar
                mano_abierta_desde = mano_abierta_desde or time.monotonic()
                if time.monotonic() - mano_abierta_desde > 1.0:
                    lienzo[:] = 0
                    mano_abierta_desde = None
            else:
                mano_abierta_desde = None
        else:
            anterior = None

        # Combinar el dibujo con la cámara
        mascara = lienzo.any(axis=2)
        frame[mascara] = cv2.addWeighted(frame, 0.2, lienzo, 0.8, 0)[mascara]

        for (nombre, c), ((x1, y1), (x2, y2)) in zip(PALETA, cajas):
            cv2.rectangle(frame, (x1, y1), (x2, y2), c, -1)
            grosor = 5 if nombre == color_nombre else 1
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), grosor)
            U.texto_centrado(frame, nombre, ((x1 + x2) // 2, (y1 + y2) // 2), 0.7)

        U.texto(frame, f"Dedos: {num_dedos}", (w - 220, 60), 1.1, (0, 255, 255))
        U.texto(frame, "1 dedo = pintar | 2 = mover | mano abierta = borrar", (20, h - 20), 0.7)

        cv2.imshow("Paso 2 - Pinta con el dedo", frame)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27):
            break
        if tecla == ord("c"):
            lienzo[:] = 0

    detector.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
