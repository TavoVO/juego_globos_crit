# Atrapa globos – visión por computadora para el CRIT

Proyecto con **OpenCV** (cámara e imágenes) y **MediaPipe** (detección de manos y cuerpo) que avanza por pasos hasta llegar a un juego de rehabilitación: atrapar globos y llevárselos al globero.

| Archivo | Qué hace |
|---|---|
| `01_camara_texto.py` | Abre la cámara y despliega texto (título, fecha, FPS). |
| `02_dedo_mano.py` | Detecta el dedo índice y permite **pintar en el aire**; cuenta dedos levantados; elegir color con el dedo. |
| `03_piernas.py` | Detecta las piernas, mide el ángulo de rodillas y cuenta **levantamientos de rodilla** pidiendo DERECHA/IZQUIERDA. |
| `04_juego_globos.py` | **El juego**: atrapar globos cerrando una pinza con pulgar e índice y entregarlos al globero según color, forma o letra. |
| `graficos.py` | Gráficos del juego (globos con sombreado 3D, globero, burbuja, menú, tipografía con acentos). |
| `utilidades.py` | Funciones compartidas (cámara, modelos, dibujo). |

---

## 1. Instalación (Mac)

```bash
cd juego_globos_crit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

La primera vez que se corre un script con MediaPipe se descarga el modelo (~5-10 MB) a la carpeta `modelos/`. Se necesita internet solo esa vez.

## 2. Correr

En **VS Code**, abre `04_juego_globos.py` y pulsa **▶ Ejecutar archivo de Python**. El archivo usa automáticamente el entorno `.venv` del proyecto si lo ejecutas con otro Python; no necesitas activar el entorno ni usar `jugar.command`. Si es la primera vez desde VS Code, acepta su solicitud de acceso a la cámara.

```bash
python 01_camara_texto.py
python 02_dedo_mano.py
python 03_piernas.py
python 04_juego_globos.py                  # abre el menú: elige Colores, Formas o Letras con el dedo
python 04_juego_globos.py --control cuerpo # mueve con las muñecas; exige pinza de la mano correspondiente
python 04_juego_globos.py --tiempo 60 --globos 4
python 04_juego_globos.py --sin-sonido
```

Teclas del juego: **1/2/3** jugar Colores/Formas/Letras · **ESPACIO** empezar · **P/ESPACIO** pausar o continuar durante la partida · **T** terminar y ver resultados · **M** menú · **R** reiniciar · **F** pantalla completa · **H** mostrar/ocultar el contorno de la mano · **Q/ESC** cerrar el juego.

**Agarrar y soltar:** abre el pulgar y el índice, coloca el índice sobre un globo y junta las dos yemas. Mantén la pinza cerrada para transportarlo al globero; abre los dedos para soltarlo. Solo se sostiene un globo a la vez, con la misma mano que lo agarró. Cada agarre requiere abrir y cerrar los dedos de nuevo; dejar el dedo encima ya no atrapa globos. El cursor se pone verde al detectar la pinza. La opción antigua `--dwell` se acepta por compatibilidad, pero ya no modifica el agarre.

Durante la partida y la cuenta regresiva aparecen los botones **Pausar/Continuar** y **Terminar**. Puedes hacer clic con el ratón o mantener el cursor de la mano sobre ellos durante 1.2 segundos. La pausa congela el tiempo, los globos y los efectos; **Terminar** muestra los resultados obtenidos hasta ese momento, incluso si estás en pausa.

El juego tiene menú (se elige con el dedo), cuenta regresiva, temporizador, rachas, confeti, sonidos de macOS y pantalla final con estrellas. La cámara se ve a color (efecto espejo) y el contorno de la mano se dibuja encima para saber dónde está el dedo.

---

## 3. Prompts sugeridos para la tarea

**Prompt 1 (OpenCV):**
> Escribe un programa en Python que use la librería OpenCV para abrir la cámara de mi computadora, mostrar el video en una ventana y desplegar un texto encima de la imagen. Que se cierre con la tecla Q. Explica cómo instalar lo necesario.

**Prompt 2 (corregir errores):**
> Corrí tu código en Python y me salió este error: `<pegar el error completo>`. Estoy en una Mac con Python 3.x. ¿Qué significa y cómo lo resuelvo paso a paso?

**Prompt 3 (MediaPipe manos):**
> Usando OpenCV y MediaPipe en Python, haz un programa que detecte la punta del dedo índice con la cámara y que al moverlo dibuje una línea en la pantalla, como si pintara en el aire. Usa la API nueva de MediaPipe Tasks (HandLandmarker).

**Prompt 4 (piernas):**
> Con MediaPipe Pose (PoseLandmarker) detecta las piernas, calcula el ángulo de la rodilla y cuenta cuántas veces levanto cada rodilla.

**Prompt 5 (juego):**
> Crea un juego con OpenCV y MediaPipe donde aparezcan globos de colores flotando; el jugador los atrapa poniendo el dedo encima y los lleva a la mano de un globero dibujado en la pantalla. El globero pide un color, forma o letra específica.

## 4. Errores comunes y cómo resolverlos

| Error | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'cv2'` | No está instalado OpenCV | `pip install opencv-python` (el paquete se llama distinto al import). |
| `ModuleNotFoundError: No module named 'mediapipe'` | No instalado o versión de Python sin soporte | `pip install mediapipe`. Si no encuentra versión, usar Python 3.10–3.12. |
| `AttributeError: module 'mediapipe' has no attribute 'solutions'` | Las versiones nuevas de MediaPipe quitaron la API vieja `mp.solutions` que muchas IAs todavía generan | Usar la API **Tasks** (`HandLandmarker`, `PoseLandmarker`), como en este proyecto. |
| La ventana sale negra / `No se pudo abrir la cámara` | macOS no le dio permiso a la Terminal o VS Code | Ajustes del Sistema → Privacidad y seguridad → Cámara → activar Terminal/VS Code y reiniciarlo. |
| `CERTIFICATE_VERIFY_FAILED` al descargar el modelo | Python de python.org en Mac sin certificados | Correr `/Applications/Python 3.x/Install Certificates.command` o `pip install certifi`. |
| Texto con `??` en lugar de acentos | `cv2.putText` no soporta acentos ni ñ | Escribir sin acentos o usar la librería Pillow para el texto. |
| `ValueError ... timestamp must be monotonically increasing` | En modo VIDEO MediaPipe exige tiempos crecientes | Usar un contador de milisegundos que siempre aumente (`MarcaTiempo` en `utilidades.py`). |
| Detecta izquierda/derecha al revés | La imagen se voltea en espejo con `cv2.flip` | Intercambiar las etiquetas (ver `03_piernas.py`). |

---

## 5. MediaPipe vs. Pose: ¿cuál es la diferencia?

Es una confusión común: **Pose no es una librería distinta, es una de las soluciones de MediaPipe.** Cuando se habla de "Pose" como alternativa casi siempre se refiere a **OpenPose** u otros modelos de estimación de pose.

- **MediaPipe** (Google) es un *framework* con varios modelos listos: **Hands** (21 puntos por mano), **Pose** (33 puntos del cuerpo), **Face Mesh** (478 puntos de la cara), **Holistic** (todo junto), gestos, segmentación, etc.
- **MediaPipe Pose** detecta **una persona** con 33 puntos (hombros, codos, muñecas, caderas, rodillas, tobillos, pies) e incluye profundidad aproximada (z) y visibilidad.
- **OpenPose** (Universidad Carnegie Mellon) detecta **varias personas a la vez** con 18–25 puntos de cuerpo, más manos y cara. Es más pesado, normalmente necesita **GPU** y su instalación es complicada.

| | MediaPipe (Hands / Pose) | OpenPose |
|---|---|---|
| Instalación | `pip install mediapipe` | Compilar o Docker, complejo |
| Hardware | Corre en laptop, celular, sin GPU | Normalmente necesita GPU |
| Personas | 1 (Pose) / hasta 2 manos (configurable) | Muchas personas a la vez |
| Puntos del cuerpo | 33 (incluye pies) | 18 o 25 |
| Velocidad | Tiempo real (~30 FPS en CPU) | Lento sin GPU |
| Uso ideal | Apps interactivas, juegos, rehabilitación en casa | Investigación, análisis de grupos, deporte |

**Conclusión para el CRIT:** MediaPipe es la mejor opción porque funciona con una laptop y cámara web común, en tiempo real, y una sola persona (el paciente) es justo el caso de uso. Para dedos y motricidad fina se usa **Hands**; para piernas, tronco y brazos, **Pose**.

---

## 6. Revisión rápida: aplicaciones de visión por computadora en rehabilitación

- **Rehabilitación física / motora:** juegos con Kinect o cámara (exergames) para rango de movimiento de hombro, alcance, equilibrio y marcha; medición automática de ángulos articulares y conteo de repeticiones; terapia en casa supervisada a distancia (p. ej. plataformas como Kaia Health o Exer, que usan la cámara del celular).
- **Parálisis cerebral:** juegos de alcance y agarre adaptados con mayor tolerancia (no exigen pinza fina), control con la cabeza o el tronco, terapia de espejo en pantalla y medición objetiva del progreso sesión a sesión.
- **Síndrome de Down:** actividades para tono muscular, coordinación y equilibrio combinadas con aprendizaje de colores, números y letras; refuerzo visual y auditivo inmediato que mantiene la motivación.
- **Autismo (TEA):** reconocimiento de emociones con detección facial, juegos de imitación de movimientos (el niño imita a un avatar), rutinas visuales predecibles y entornos de baja estimulación que se pueden ajustar.
- **Adultos mayores / neurológico (EVC):** ejercicios de miembro superior, prevención de caídas y estimulación cognitiva combinada con movimiento.

Ideas clave que se repiten: **retroalimentación inmediata**, **dificultad ajustable**, **medición del progreso** y **motivación por juego**.

---

## 7. Propuesta para el CRIT: "El globero"

**Objetivo:** juego de rehabilitación que combina **movimiento físico** (alcance del brazo, coordinación ojo-mano, motricidad de hombro y piernas) con **estimulación cognitiva** (colores, formas, letras, lateralidad, atención y seguimiento de instrucciones).

**Dinámica:** aparecen globos flotando. El globero pide uno ("Dame un globo ROJO" / "...con TRIÁNGULO" / "...con la letra M"). El niño lo atrapa juntando pulgar e índice sobre el globo y lo lleva hasta la mano del globero manteniendo la pinza cerrada.

**Por qué funciona para distintas poblaciones:**

- *Adaptación motora:* la cantidad de globos se ajusta con `--globos`. El agarre actual requiere pinza con pulgar e índice; en `--control cuerpo` se mueve con la muñeca y se exige la pinza de esa mano. El terapeuta puede pausar o terminar la actividad en cualquier momento.
- *Síndrome de Down:* refuerza colores, formas y vocales con recompensa visual inmediata ("MUY BIEN!", racha, el ramo del globero crece).
- *Autismo:* instrucción única, clara y visual; sin castigos (un error no resta puntos, solo recuerda qué buscar).
- *Piernas:* `03_piernas.py` (marcha con indicación DERECHA/IZQUIERDA) se puede convertir en un nivel donde se "patea" o se sube la rodilla para reventar globos.

**Lo que registra el juego:** puntos, globos correctos, precisión. **Siguientes pasos:** guardar cada sesión en un CSV (fecha, paciente, aciertos, tiempo de reacción) para que el terapeuta vea la evolución; agregar sonido y voz para pacientes que aún no leen; un nivel de números (contar globos) y uno de secuencias (primero rojo, luego azul).
