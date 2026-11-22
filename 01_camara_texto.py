"""
PASO 1 - OpenCV: abrir la cámara y desplegar texto sobre la imagen.

Ejecutar:  python 01_camara_texto.py
Teclas:    S = guardar foto   |   Q o ESC = salir
"""
import argparse
import time

import cv2

from utilidades import ContadorFPS, abrir_camara, texto, texto_centrado


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camara", type=int, default=0)
    args = parser.parse_args()

    cap = abrir_camara(args.camara)
    fps = ContadorFPS()

    while True:
        ok, frame = cap.read()
        if not ok:
            print("No llegó imagen de la cámara.")
            break

        frame = cv2.flip(frame, 1)  # efecto espejo
        h, w = frame.shape[:2]

        texto_centrado(frame, "Hola CRIT!", (w // 2, 70), escala=2.0, color=(0, 220, 255), grosor=4)
        texto(frame, time.strftime("%d/%m/%Y  %H:%M:%S"), (20, h - 60), 0.8)
        texto(frame, f"FPS: {fps.tick():.0f}   Resolucion: {w}x{h}", (20, h - 20), 0.7)
        texto(frame, "S = foto   Q = salir", (w - 300, h - 20), 0.7, (0, 255, 0))

        cv2.imshow("Paso 1 - Camara con texto", frame)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27):
            break
        if tecla == ord("s"):
            nombre = time.strftime("foto_%H%M%S.png")
            cv2.imwrite(nombre, frame)
            print("Guardada", nombre)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
