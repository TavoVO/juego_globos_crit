"""Historial local de partidas. Cada línea contiene un resultado completo."""
from dataclasses import asdict, dataclass
import json
import os


@dataclass(frozen=True)
class Puntuacion:
    fecha: str
    categoria: str
    velocidad: str
    puntos: int
    aciertos: int


class Historial:
    def __init__(self, archivo=None):
        self.archivo = archivo
        self.partidas = []
        self.error = None
        if archivo is not None:
            try:
                for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        registro = Puntuacion(**json.loads(linea))
                    except (TypeError, ValueError):
                        continue
                    if (all(isinstance(campo, str) for campo in (registro.fecha, registro.categoria, registro.velocidad))
                            and all(isinstance(n, int) and n >= 0 for n in (registro.puntos, registro.aciertos))):
                        self.partidas.append(registro)
            except FileNotFoundError:
                pass
            except OSError as exc:
                print(f"No se pudo leer el historial: {exc}")
                self.error = "No se pudo leer el historial guardado."

    def agregar(self, partida):
        self.partidas.append(partida)
        if self.archivo is not None:
            try:
                linea = (json.dumps(asdict(partida), ensure_ascii=False) + "\n").encode("utf-8")
                with self.archivo.open("a+b") as archivo:
                    if archivo.tell():
                        archivo.seek(-1, os.SEEK_END)
                        if archivo.read(1) != b"\n":
                            linea = b"\n" + linea
                    archivo.write(linea)
            except OSError as exc:
                print(f"No se pudo guardar la puntuación: {exc}")
                self.error = "Algunos resultados de esta sesión no se pudieron guardar."
