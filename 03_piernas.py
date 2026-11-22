"""
PASO 3 - MediaPipe Pose: detectar movimiento de piernas.

Ejercicio "marcha en su lugar": el programa pide levantar la rodilla
DERECHA o IZQUIERDA (componente cognitivo: lateralidad) y cuenta las
repeticiones correctas. También muestra el ángulo de cada rodilla.

Colócate a 2-3 metros de la cámara para que se vea todo el cuerpo.

Ejecutar:  python 03_piernas.py
Teclas:    R = reiniciar   |   Q o ESC = salir
"""
import argparse
import math
import random

import cv2

import utilidades as U

# Índices de MediaPipe Pose: hombro, cadera, rodilla, tobillo.
# Como la imagen se voltea en espejo ANTES de detectar, MediaPipe ve los
# lados invertidos: la pierna "right" (24/26/28) del modelo es la IZQUIERDA real.
LADOS = {
    "IZQUIERDA": {"hombro": 12, "cadera": 24, "rodilla": 26, "tobillo": 28},
    "DERECHA": {"hombro": 11, "cadera": 23, "rodilla": 25, "tobillo": 27},
}
COLOR_LADO = {"IZQUIERDA": (255, 160, 0), "DERECHA": (0, 160, 255)}

ANGULO_ARRIBA = 125    # ángulo hombro-cadera-rodilla: rodilla levantada
ANGULO_ABAJO = 155     # pierna de nuevo abajo


def angulo(a, b, c):
    """Ángulo ABC en grados."""
    ang = math.degrees(
        math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    )
    ang = abs(ang)
    return 360 - ang if ang > 180 else ang


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camara", type=int, default=0)
    args = parser.parse_args()

    cap = U.abrir_camara(args.camara)
    detector = U.crear_detector_pose()
    reloj = U.MarcaTiempo()

    def reiniciar():
        return {"correctas": 0, "incorrectas": 0, "pedido": random.choice(list(LADOS)),
                "arriba": {l: False for l in LADOS}, "mensaje": "", "msg_frames": 0}

    est = reiniciar()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        res = detector.detect_for_video(U.a_imagen_mp(frame), reloj.ms())

        if res.pose_landmarks:
            lm = res.pose_landmarks[0]
            px = lambda i: (int(lm[i].x * w), int(lm[i].y * h))

            for lado, idx in LADOS.items():
                hom, cad, rod, tob = (px(idx[k]) for k in ("hombro", "cadera", "rodilla", "tobillo"))
                col = COLOR_LADO[lado]
                cv2.line(frame, hom, cad, col, 4)
                cv2.line(frame, cad, rod, col, 6)
                cv2.line(frame, rod, tob, col, 6)
                for p in (cad, rod, tob):
                    cv2.circle(frame, p, 8, (255, 255, 255), -1)

                ang_cadera = angulo(hom, cad, rod)
                ang_rodilla = angulo(cad, rod, tob)
                U.texto(frame, f"{ang_rodilla:.0f}", (rod[0] + 15, rod[1]), 0.7, col)

                # Detección de "levantar rodilla" con histéresis para no contar doble
                if not est["arriba"][lado] and ang_cadera < ANGULO_ARRIBA:
                    est["arriba"][lado] = True
                    if lado == est["pedido"]:
                        est["correctas"] += 1
                        est["mensaje"] = "MUY BIEN!"
                        est["pedido"] = random.choice(list(LADOS))
                    else:
                        est["incorrectas"] += 1
                        est["mensaje"] = f"Esa es la {lado}"
                    est["msg_frames"] = 30
                elif est["arriba"][lado] and ang_cadera > ANGULO_ABAJO:
                    est["arriba"][lado] = False
        else:
            U.texto_centrado(frame, "Alejate para que se vea todo tu cuerpo", (w // 2, h // 2), 1.0, (0, 255, 255))

        pedido = est["pedido"]
        U.texto_centrado(frame, f"Levanta la rodilla {pedido}", (w // 2, 60), 1.4, COLOR_LADO[pedido], 3)
        U.texto(frame, f"Correctas: {est['correctas']}   Intentos fallidos: {est['incorrectas']}", (20, h - 20), 0.8)
        if est["msg_frames"] > 0:
            est["msg_frames"] -= 1
            U.texto_centrado(frame, est["mensaje"], (w // 2, 140), 1.6, (0, 255, 0), 4)

        cv2.imshow("Paso 3 - Piernas", frame)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27):
            break
        if tecla == ord("r"):
            est = reiniciar()

    detector.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
