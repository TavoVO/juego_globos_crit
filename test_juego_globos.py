"""Pruebas de gestos y estados sin abrir la cámara ni una ventana."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as Datos
import sys
import subprocess
from tempfile import TemporaryDirectory
import unicodedata
import unittest
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location("globos", Path(__file__).with_name("04_juego_globos.py"))
globos = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = globos
spec.loader.exec_module(globos)


class ArranqueTests(unittest.TestCase):
    def test_rutas_con_acentos_no_generan_bucle_de_reinicio(self):
        script = Path(__file__).with_name("04_juego_globos.py").resolve()
        python_local = script.parent / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if not python_local.is_file():
            self.skipTest("Requiere el entorno instalado del juego")
        for forma_python, forma_script in (("NFC", "NFD"), ("NFD", "NFC")):
            ejecutable = unicodedata.normalize(forma_python, str(python_local))
            archivo = unicodedata.normalize(forma_script, str(script))
            if not Path(ejecutable).exists() or not Path(archivo).exists():
                continue
            with self.subTest(python=forma_python, script=forma_script):
                resultado = subprocess.run([ejecutable, archivo, "--help"],
                                           capture_output=True, text=True, timeout=10)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertIn("usage:", resultado.stdout)
                self.assertNotIn("Usando el entorno", resultado.stdout)


class JuegoTests(unittest.TestCase):
    def setUp(self):
        self.ahora = 100.0
        reloj = patch.object(globos.time, "monotonic", side_effect=lambda: self.ahora)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.juego = globos.Juego(1280, 720, 90, 3, lambda _: None)
        self.juego.empezar()
        self.g = self.juego.globos[0]
        for i, g in enumerate(self.juego.globos):
            g.x, g.y, g.vy, g.fase = 250 + i * 180, 300, 0, 0
        self.juego.objetivo = self.g.color

    def cursor(self, pinza=False, pos=(250, 300), mano="Left"):
        return globos.Cursor(pos, mano, pinza)

    def tick(self, *cursores, dt=0.1):
        self.ahora += dt
        self.juego.actualizar(list(cursores), dt, 0)

    def agarrar(self):
        self.tick(self.cursor())
        self.tick(self.cursor(True))
        self.assertIs(self.juego.sostenido, self.g)

    def test_dedo_abierto_no_atrapa_aunque_permanezca_encima(self):
        for _ in range(30):
            self.tick(self.cursor())
        self.assertIsNone(self.juego.sostenido)

    def test_pinza_agarrar_y_abrir_suelta(self):
        self.agarrar()
        self.tick(self.cursor(False))
        self.assertIsNone(self.juego.sostenido)
        self.assertFalse(self.g.agarrado)

    def test_pinza_ya_cerrada_no_atrapa_al_entrar(self):
        self.tick(self.cursor(True, (50, 200)))
        self.tick(self.cursor(True))
        self.assertIsNone(self.juego.sostenido)
        self.agarrar()

    def test_cerrar_fuera_del_globo_no_atrapa_al_moverse(self):
        self.tick(self.cursor(False, (50, 200)))
        self.tick(self.cursor(True, (50, 200)))
        self.tick(self.cursor(True))
        self.assertIsNone(self.juego.sostenido)

    def test_otra_mano_no_roba_globo_y_perder_mano_lo_suelta(self):
        self.agarrar()
        posicion = self.g.centro()
        self.tick(self.cursor(True, (600, 300), "Right"))
        self.assertEqual(self.g.centro(), posicion)
        for _ in range(11):
            self.tick(self.cursor(True, (600, 300), "Right"))
        self.assertIsNone(self.juego.sostenido)

    def test_entrega_correcta_y_no_reagarra_con_pinza_cerrada(self):
        self.agarrar()
        self.tick(self.cursor(True, self.juego.zona))
        self.assertEqual(self.juego.aciertos, 1)
        self.assertIsNone(self.juego.sostenido)
        self.g.x, self.g.y = 250, 300
        self.tick(self.cursor(True))
        self.assertIsNone(self.juego.sostenido)

    def test_pausa_congela_tiempo_globos_y_efectos(self):
        self.agarrar()
        self.juego.efectos.confeti(200, 200, n=1)
        self.juego.alternar_pausa()
        restante = self.juego.tiempo_restante()
        posicion, animacion = self.g.centro(), self.juego.t_animacion
        particula = list(self.juego.efectos.particulas[0])
        self.ahora += 50
        self.tick(self.cursor(True, (600, 300)))
        frame = np.zeros((720, 1280, 3), np.uint8)
        self.juego.dibujar(frame, [], [], 1000, 0.1, False)
        self.assertEqual(self.juego.tiempo_restante(), restante)
        self.assertEqual(self.g.centro(), posicion)
        self.assertEqual(self.juego.t_animacion, animacion)
        self.assertEqual(self.juego.efectos.particulas[0], particula)
        self.juego.alternar_pausa()
        self.assertAlmostEqual(self.juego.tiempo_restante(), restante)
        self.assertEqual(self.juego.estado, "jugando")

    def test_cuenta_regresiva_tambien_se_pausa(self):
        self.juego.iniciar_cuenta("FORMAS")
        self.ahora += 1
        self.juego.alternar_pausa()
        self.ahora += 30
        self.juego.alternar_pausa()
        self.tick()
        self.assertEqual(self.juego.estado, "cuenta")
        self.ahora += 3
        self.tick()
        self.assertEqual(self.juego.estado, "jugando")

    def test_botones_clic_pausar_continuar_y_terminar(self):
        def clic(clave):
            x, y, w, h = self.juego.controles[clave]
            self.juego.clic(x + w // 2, y + h // 2)
        clic("pausa")
        self.assertEqual(self.juego.estado, "pausa")
        clic("pausa")
        self.assertEqual(self.juego.estado, "jugando")
        self.juego.aciertos, self.juego.puntos = 2, 25
        self.agarrar()
        clic("pausa")
        clic("terminar")
        self.assertEqual(self.juego.estado, "fin")
        self.assertEqual((self.juego.aciertos, self.juego.puntos), (2, 25))
        self.assertIsNone(self.juego.sostenido)

    def test_hover_pausar_no_se_repite_sin_retirar_mano(self):
        x, y, w, h = self.juego.controles["pausa"]
        cursor = self.cursor(pos=(x + w // 2, y + h // 2))
        for _ in range(35):
            self.tick(cursor)
        self.assertEqual(self.juego.estado, "pausa")
        self.tick(self.cursor())
        for _ in range(13):
            self.tick(cursor)
        self.assertEqual(self.juego.estado, "jugando")


class PinzaTests(unittest.TestCase):
    def resultado(self, distancia, escala=1):
        # Coordenadas de una palma de 100 px de ancho en un lienzo de 1000 px.
        pts = [Datos(x=0.5, y=0.5) for _ in range(21)]
        for idx, x, y in ((0, .5, .6), (9, .5, .5), (5, .45, .5), (17, .55, .5),
                          (8, .5, .4), (4, .5 + distancia / 1000, .4)):
            pts[idx] = Datos(x=x * escala, y=y * escala)
        return Datos(hand_landmarks=[pts], handedness=[[Datos(category_name="Left")]])

    def test_umbral_relativo_histeresis_y_perdida(self):
        estados = {}
        for distancia, esperado in ((60, False), (25, True), (40, True), (55, False), (40, False)):
            cursores, _ = globos.leer_cursores(self.resultado(distancia), 1000, 1000, "mano", estados)
            self.assertEqual(cursores[0].pinza, esperado)
        cursores, _ = globos.leer_cursores(self.resultado(25, .5), 1000, 1000, "mano", {})
        self.assertTrue(cursores[0].pinza)
        globos.leer_cursores(Datos(hand_landmarks=[]), 1000, 1000, "mano", estados)
        self.assertEqual(estados, {})

    def test_cuerpo_sin_mano_no_puede_agarrar(self):
        cuerpo = [Datos(x=.5, y=.6, visibility=1) for _ in range(33)]
        res = Datos(pose_landmarks=[cuerpo])
        cursores, _ = globos.leer_cursores(res, 1000, 1000, "cuerpo", {})
        self.assertFalse(any(c.pinza for c in cursores))
        cursores, _ = globos.leer_cursores(res, 1000, 1000, "cuerpo", {}, self.resultado(25))
        self.assertTrue(all(c.pinza for c in cursores))


class OpcionesJuegoTests(unittest.TestCase):
    def clic(self, juego, clave):
        x, y, w, h = juego.botones_visibles()[clave]
        juego.clic(x + w // 2, y + h // 2)

    def test_tres_opciones_visibles_y_distintas_en_cada_categoria(self):
        juego = globos.Juego(1280, 720, 90, 3, lambda _: None)
        categorias = {"COLORES": {"ROJO", "AZUL", "AMARILLO"},
                      "FORMAS": {"CIRCULO", "CUADRADO", "TRIANGULO"},
                      "LETRAS": {"A", "B", "C"}}
        for categoria, esperados in categorias.items():
            juego.ir_menu()
            self.clic(juego, categoria)
            self.assertTrue(all(g.visible() for g in juego.globos))
            for g in juego.globos:
                g.reiniciar()
            self.assertEqual({g.atributo(categoria) for g in juego.globos}, esperados)

    def test_velocidad_cambia_desplazamiento_sin_cambiar_temporizador(self):
        juego = globos.Juego(1280, 720, 90, 3, lambda _: None)
        movimientos = []
        with patch.object(globos.time, "monotonic", return_value=100) as reloj:
            for velocidad in ("Lenta", "Normal", "Rápida"):
                juego.ir_menu()
                self.clic(juego, velocidad)
                juego.empezar()
                globo = juego.globos[0]
                globo.y, globo.vy = 450, 60
                reloj.return_value = juego.inicio + 0.1
                juego.actualizar([], 0.1, 0)
                movimientos.append(450 - globo.y)
                self.assertAlmostEqual(juego.tiempo_restante(), 89.9)
        self.assertLess(movimientos[0], movimientos[1])
        self.assertLess(movimientos[1], movimientos[2])

    def test_fondo_muestra_video_nitido_e_independiente_del_lienzo(self):
        juego = globos.Juego(1280, 720, 90, 3, lambda _: None)
        self.clic(juego, "Fondo")
        self.assertEqual(juego.vista, "Fondo")
        camara = np.full((720, 1280, 3), (50, 180, 240), dtype=np.uint8)
        cuadro = globos.crear_fondo(1280, 720)
        juego.dibujar(cuadro, [], [], 0, 0, False, imagen_camara=camara)
        x, y, w, h = juego.rect_camara
        np.testing.assert_array_equal(cuadro[y + h // 2, x + w // 2], camara[0, 0])
        self.assertFalse(np.array_equal(cuadro[0, 0], camara[0, 0]))
        self.clic(juego, "Cámara")
        self.assertEqual(juego.vista, "Cámara")

    def test_historial_conserva_partidas_terminadas_y_puede_navegarse(self):
        with TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "partidas.jsonl"
            juego = globos.Juego(1280, 720, 90, 3, lambda _: None, archivo)
            juego.iniciar_cuenta("LETRAS")
            juego.terminar()    # La cuenta regresiva todavía no cuenta como partida.
            self.assertFalse(archivo.exists())
            for i in range(8):
                juego.ir_menu()
                self.clic(juego, "Rápida")
                self.clic(juego, "FORMAS")
                juego.empezar()
                juego.puntos, juego.aciertos = i * 10, i
                juego.alternar_pausa()
                self.clic(juego, "terminar")
            juego.terminar()    # No se registra una partida terminada dos veces.
            self.clic(juego, "historial")
            self.assertEqual(juego.paginas_historial(), 2)
            self.clic(juego, "siguiente")
            self.assertEqual(juego.pagina_historial, 1)
            self.clic(juego, "volver")
            self.assertEqual(juego.estado, "fin")
            otro = globos.Juego(1280, 720, 90, 3, lambda _: None, archivo)
            self.assertEqual([p.puntos for p in otro.historial.partidas], list(range(0, 80, 10)))
            self.assertEqual((otro.historial.partidas[-1].categoria, otro.historial.partidas[-1].velocidad),
                             ("Formas", "Rápida"))

    def test_historial_tolera_linea_incompleta_sin_perder_la_siguiente(self):
        with TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "partidas.jsonl"
            archivo.write_text('{"fecha":', encoding="utf-8")
            historial = globos.Historial(archivo)
            registro = globos.Puntuacion("24/11/26 12:00", "Colores", "Normal", 15, 1)
            historial.agregar(registro)
            self.assertEqual(globos.Historial(archivo).partidas, [registro])

    def test_el_nombre_se_edita_en_menu_y_se_guarda_por_partida(self):
        with TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "partidas.jsonl"
            juego = globos.Juego(1280, 720, 90, 3, lambda _: None, archivo)
            x, y, w, h = juego.campo_nombre
            juego.clic(x + w // 2, y + h // 2)
            for letra in "  Joaquín   Pérezx ":
                self.assertTrue(juego.escribir_nombre(ord(letra)))
            juego.escribir_nombre(8)
            juego.escribir_nombre(8)
            juego.escribir_nombre(13)
            self.assertEqual(juego.nombre, "Joaquín Pérez")
            self.assertFalse(juego.escribir_nombre(ord("q")))
            self.clic(juego, "COLORES")
            juego.empezar()
            juego.puntos = 20
            juego.terminar()

            juego.ir_menu()
            juego.clic(x + w // 2, y + h // 2)
            juego.escribir_nombre(ord("X"))
            juego.escribir_nombre(27)
            self.assertEqual(juego.nombre, "Joaquín Pérez")
            juego.clic(x + w // 2, y + h // 2)
            for _ in juego.nombre:
                juego.escribir_nombre(8)
            for letra in "Luz":
                juego.escribir_nombre(ord(letra))
            self.clic(juego, "LETRAS")   # Elegir categoría también confirma el campo.
            juego.empezar()
            juego.puntos = 10
            juego.terminar()

            filas = globos.Historial(archivo).partidas
            self.assertEqual([(f.nombre, f.puntos) for f in filas], [("Joaquín Pérez", 20), ("Luz", 10)])

    def test_historial_conserva_puntajes_anteriores_a_los_nombres(self):
        with TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "partidas.jsonl"
            fila = {"fecha": "24/11/26 12:00", "categoria": "Colores", "velocidad": "Normal",
                    "puntos": 30, "aciertos": 2}
            archivo.write_text(json.dumps(fila) + "\n", encoding="utf-8")
            historial = globos.Historial(archivo)
            self.assertEqual([(f.nombre, f.puntos) for f in historial.partidas], [("Sin nombre", 30)])


if __name__ == "__main__":
    unittest.main()
