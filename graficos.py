"""
Gráficos del juego: todo se dibuja UNA vez con Pillow (con suavizado) y se
guarda en caché como "sprite" (imagen con transparencia). En cada cuadro solo
se pegan los sprites sobre la imagen de la cámara, así el juego va fluido.

Los colores se escriben en RGB; los sprites se regresan en BGRA (formato de OpenCV).
"""
import functools
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

COLORES_GLOBO = {
    "ROJO": (235, 60, 60),
    "AZUL": (45, 125, 245),
    "AMARILLO": (252, 205, 25),
}
FORMAS_GLOBO = ("CIRCULO", "CUADRADO", "TRIANGULO")
LETRAS_GLOBO = ("A", "B", "C")

TINTA = (35, 40, 60)          # texto oscuro
DORADO = (255, 196, 30)

_FUENTES = [
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",   # Mac
    "/Library/Fonts/Arial Rounded Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",                                 # Windows
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",         # Linux
]


@functools.lru_cache(maxsize=None)
def fuente(tam):
    tam = max(8, int(tam))
    for ruta in _FUENTES:
        if os.path.exists(ruta):
            try:
                return ImageFont.truetype(ruta, tam)
            except OSError:
                pass
    try:
        return ImageFont.load_default(tam)
    except TypeError:
        return ImageFont.load_default()


# ----------------------------------------------------------------------------
# Conversión y pegado
# ----------------------------------------------------------------------------
def pil_a_bgra(img):
    a = np.array(img.convert("RGBA"))
    return np.ascontiguousarray(a[..., [2, 1, 0, 3]])


def bgra_a_pil(spr):
    return Image.fromarray(np.ascontiguousarray(spr[..., [2, 1, 0, 3]]), "RGBA")


def bgr(rgb):
    return (int(rgb[2]), int(rgb[1]), int(rgb[0]))


def pegar(dst, spr, x, y, alpha=1.0):
    """Pega un sprite BGRA sobre dst (BGR) con su esquina superior izquierda en (x, y)."""
    x, y = int(x), int(y)
    h, w = spr.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1 or alpha <= 0:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3].astype(np.float32) * (min(alpha, 1.0) / 255.0)
    roi = dst[y0:y1, x0:x1]
    cv2.blendLinear(s[..., :3], roi, a, 1.0 - a, dst=roi)


def pegar_centro(dst, spr, cx, cy, alpha=1.0):
    pegar(dst, spr, cx - spr.shape[1] / 2, cy - spr.shape[0] / 2, alpha)


def pegar_izq(dst, spr, x, cy, alpha=1.0):
    pegar(dst, spr, x, cy - spr.shape[0] / 2, alpha)


# ----------------------------------------------------------------------------
# Texto
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=2048)
def sprite_texto(txt, tam, color=(255, 255, 255), borde=0, color_borde=TINTA, sombra=True):
    f = fuente(tam)
    l, t, r, b = f.getbbox(txt, stroke_width=borde)
    m = int(tam * 0.15) + 4
    w, h = r - l + 2 * m, b - t + 2 * m
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    org = (m - l, m - t)
    if sombra:
        capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((org[0], org[1] + tam * 0.06), txt, font=f, fill=(0, 0, 0, 150),
                                  stroke_width=borde, stroke_fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img, capa.filter(ImageFilter.GaussianBlur(max(1, tam * 0.05))))
    ImageDraw.Draw(img).text(org, txt, font=f, fill=tuple(color) + (255,),
                             stroke_width=borde, stroke_fill=tuple(color_borde) + (255,))
    return pil_a_bgra(img)


# ----------------------------------------------------------------------------
# Paneles, píldoras, círculos y brillos
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=512)
def sprite_panel(w, h, color=(20, 24, 45), alpha=185, radio=22, borde=None, grosor=3):
    ss = 3
    img = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, w * ss - 1, h * ss - 1), radio * ss, fill=tuple(color) + (alpha,),
        outline=(tuple(borde) + (255,)) if borde else None, width=grosor * ss)
    return pil_a_bgra(img.resize((w, h), Image.LANCZOS))


@functools.lru_cache(maxsize=256)
def sprite_pildora(txt, tam, fondo, color=(255, 255, 255)):
    t = sprite_texto(txt, tam, color, sombra=False)
    h = int(tam * 1.7)
    w = t.shape[1] + h
    p = bgra_a_pil(sprite_panel(w, h, fondo, 235, h // 2, (255, 255, 255), max(2, tam // 12)))
    p.alpha_composite(bgra_a_pil(t), ((w - t.shape[1]) // 2, (h - t.shape[0]) // 2))
    return pil_a_bgra(p)


@functools.lru_cache(maxsize=64)
def sprite_brillo(radio, rgb):
    """Círculo con degradado radial (para el cursor y la zona de entrega)."""
    d = radio * 2
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32)
    r = np.sqrt((xx - radio) ** 2 + (yy - radio) ** 2) / radio
    a = np.clip(1 - r, 0, 1) ** 1.8
    rgba = np.zeros((d, d, 4), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = rgb[2], rgb[1], rgb[0]
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return rgba


@functools.lru_cache(maxsize=32)
def sprite_estrella(tam, llena=True):
    ss = 3
    s = tam * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = _puntos_estrella(s / 2, s / 2 + s * 0.04, s * 0.48, 0.45)
    if llena:
        d.polygon(pts, fill=DORADO + (255,), outline=(200, 130, 0, 255), width=int(s * 0.05))
        brillo = _puntos_estrella(s / 2, s / 2 + s * 0.04, s * 0.30, 0.45)
        d.polygon(brillo, fill=(255, 225, 110, 255))
    else:
        d.polygon(pts, fill=(80, 85, 105, 200), outline=(150, 155, 175, 255), width=int(s * 0.04))
    return pil_a_bgra(img.resize((tam, tam), Image.LANCZOS))


def _puntos_estrella(cx, cy, r, interior=0.45):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * interior
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def dibujar_forma(d, forma, c, s, relleno, contorno=None, grosor=0):
    x, y = c
    kw = dict(fill=relleno, outline=contorno, width=int(grosor))
    if forma == "CIRCULO":
        d.ellipse((x - s, y - s, x + s, y + s), **kw)
    elif forma == "CUADRADO":
        d.rounded_rectangle((x - s * 0.9, y - s * 0.9, x + s * 0.9, y + s * 0.9), s * 0.15, **kw)
    elif forma == "TRIANGULO":
        d.polygon([(x, y - s * 1.05), (x - s * 1.05, y + s * 0.8), (x + s * 1.05, y + s * 0.8)], **kw)
    elif forma == "ESTRELLA":
        d.polygon(_puntos_estrella(x, y + s * 0.08, s * 1.15, 0.45), **kw)


@functools.lru_cache(maxsize=32)
def sprite_forma(forma, tam, rgb):
    ss = 3
    s = tam * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dibujar_forma(ImageDraw.Draw(img), forma, (s / 2, s / 2), s * 0.4, tuple(rgb) + (255,),
                  (255, 255, 255, 255), s * 0.05)
    return pil_a_bgra(img.resize((tam, tam), Image.LANCZOS))


# ----------------------------------------------------------------------------
# Globo con sombreado 3D
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=512)
def sprite_globo(rgb, r, tipo=None, simbolo=None):
    """Regresa (sprite, cx, cy, y_nudo): centro del globo y parte baja del nudo dentro del sprite."""
    ss = 3
    R = r * ss
    W, H = int(R * 2.3), int(R * 2.75)
    cx, cy = W / 2, R * 1.22
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ny = (yy - cy) / (R * 1.15)
    nx = (xx - cx) / (R * (1 - 0.12 * np.clip(ny, 0, None)))   # más angosto abajo (forma de globo)
    d = nx ** 2 + ny ** 2
    nz = np.sqrt(np.clip(1 - d, 0, 1))
    L = np.array([-0.45, -0.6, 0.66], np.float32)
    L /= np.linalg.norm(L)
    luz = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    base = np.array(rgb, np.float32) / 255
    col = base * (0.55 + 0.55 * luz[..., None])
    borde = (1 - nz) ** 3 * np.clip(nx * 0.6 + ny * 0.6, 0, 1)     # luz de rebote abajo a la derecha
    col += borde[..., None] * 0.22
    col += (luz ** 45)[..., None] * 0.85                            # brillo especular
    col = np.clip(col, 0, 1)
    alpha = (d <= 1).astype(np.float32) * 0.97
    img = Image.fromarray(np.dstack([col * 255, alpha * 255]).astype(np.uint8), "RGBA")

    # reflejo suave
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).ellipse((cx - R * 0.6, cy - R * 0.85, cx - R * 0.18, cy - R * 0.3), fill=(255, 255, 255, 90))
    img = Image.alpha_composite(img, capa.filter(ImageFilter.GaussianBlur(R * 0.07)))

    dr = ImageDraw.Draw(img)
    k = R * 0.14
    ky = cy + R * 1.13
    oscuro = tuple(int(c * 0.72) for c in rgb) + (255,)
    dr.polygon([(cx, ky - k * 0.5), (cx - k, ky + k * 0.9), (cx + k, ky + k * 0.9)], fill=oscuro)

    if tipo == "FORMAS":
        dibujar_forma(dr, simbolo, (cx, cy + R * 0.05), R * 0.42, (255, 255, 255, 255),
                      (30, 30, 50, 160), R * 0.04)
    elif tipo == "LETRAS":
        dr.text((cx, cy + R * 0.02), simbolo, font=fuente(R * 1.05), anchor="mm", fill=(255, 255, 255, 255),
                stroke_width=int(R * 0.06), stroke_fill=(30, 30, 50, 200))

    img = img.resize((W // ss, H // ss), Image.LANCZOS)
    return pil_a_bgra(img), cx / ss, cy / ss, (ky + k * 0.9) / ss


# ----------------------------------------------------------------------------
# El globero
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=4)
def sprite_globero(altura):
    """Regresa (sprite, x_mano, y_mano)."""
    ss = 3
    u = altura * ss / 100.0
    W, H = int(72 * u), int(100 * u)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def P(x, y):
        return (x * u, y * u)

    def caja(x1, y1, x2, y2):
        return [P(x1, y1), P(x2, y2)]

    # sombra en el piso
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).ellipse(caja(22, 94.5, 64, 99.5), fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(u * 1.2)))
    d = ImageDraw.Draw(img)

    piel, piel_os = (248, 204, 165, 255), (226, 168, 128, 255)
    rojo, rojo_os = (220, 45, 55, 255), (170, 30, 40, 255)
    azul, azul_os = (45, 70, 140, 255), (30, 48, 100, 255)
    cafe = (70, 45, 30, 255)

    def linea(x1, y1, x2, y2, g, col):
        d.line([P(x1, y1), P(x2, y2)], fill=col, width=int(g * u))
        for x, y in ((x1, y1), (x2, y2)):
            d.ellipse(caja(x - g / 2, y - g / 2, x + g / 2, y + g / 2), fill=col)

    # piernas y zapatos
    linea(37.5, 72, 36, 92, 7, azul_os)
    linea(46.5, 72, 48, 92, 7, azul_os)
    d.ellipse(caja(28, 89.5, 40, 96.5), fill=cafe)
    d.ellipse(caja(44, 89.5, 57, 96.5), fill=cafe)

    # brazo de atrás (mano en la cintura)
    linea(53, 47, 59, 57, 5.5, rojo_os)
    linea(59, 57, 55, 65, 4.6, piel_os)

    # torso a rayas
    mascara = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(caja(30, 43, 54, 74), radius=int(7 * u), fill=255)
    rayas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    drr = ImageDraw.Draw(rayas)
    y = 43.0
    while y < 75:
        drr.rectangle(caja(0, y, 72, y + 2.6), fill=rojo)
        y += 5.2
    img.paste(rayas, (0, 0), mascara)
    d = ImageDraw.Draw(img)

    # pantalón con tirantes
    d.rounded_rectangle(caja(30.5, 66, 53.5, 76), radius=int(3 * u), fill=azul)
    linea(35, 44, 36, 67, 2.4, azul)
    linea(49, 44, 48, 67, 2.4, azul)
    d.ellipse(caja(34.8, 64.8, 37.2, 67.2), fill=DORADO + (255,))
    d.ellipse(caja(46.8, 64.8, 49.2, 67.2), fill=DORADO + (255,))

    # brazo levantado (manga + antebrazo + mano)
    linea(33, 47, 24, 37, 5.8, rojo)
    linea(24, 37, 14, 24, 4.6, piel)
    d.ellipse(caja(9.5, 17.5, 18.5, 26.5), fill=piel)
    d.ellipse(caja(15.5, 20, 19.5, 24.5), fill=piel_os)       # pulgar

    # cuello y moño
    d.rectangle(caja(39.5, 40, 44.5, 45), fill=piel_os)
    d.polygon([P(42, 45), P(36.5, 42.2), P(36.5, 47.8)], fill=DORADO + (255,))
    d.polygon([P(42, 45), P(47.5, 42.2), P(47.5, 47.8)], fill=DORADO + (255,))
    d.ellipse(caja(40.6, 43.6, 43.4, 46.4), fill=(225, 160, 10, 255))

    # cabeza
    d.ellipse(caja(29.5, 30, 34.5, 37), fill=piel_os)
    d.ellipse(caja(49.5, 30, 54.5, 37), fill=piel_os)
    d.ellipse(caja(31.5, 21.5, 52.5, 43), fill=piel)
    # mejillas
    mej = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dm = ImageDraw.Draw(mej)
    dm.ellipse(caja(33.5, 34.5, 38.5, 38.5), fill=(255, 120, 120, 110))
    dm.ellipse(caja(45.5, 34.5, 50.5, 38.5), fill=(255, 120, 120, 110))
    img = Image.alpha_composite(img, mej.filter(ImageFilter.GaussianBlur(u * 0.6)))
    d = ImageDraw.Draw(img)
    # ojos
    for ox in (36, 43.5):
        d.ellipse(caja(ox, 28.5, ox + 4.5, 33.5), fill=(255, 255, 255, 255))
        d.ellipse(caja(ox + 1.2, 29.6, ox + 4.0, 32.9), fill=(30, 30, 40, 255))
        d.ellipse(caja(ox + 2.6, 30.0, ox + 3.6, 31.0), fill=(255, 255, 255, 255))
    d.arc(caja(35.5, 25.5, 40.5, 28.5), 200, 340, fill=cafe, width=int(0.9 * u))
    d.arc(caja(43.5, 25.5, 48.5, 28.5), 200, 340, fill=cafe, width=int(0.9 * u))
    # nariz, bigote, sonrisa
    d.ellipse(caja(40.3, 32.2, 43.7, 36.2), fill=piel_os)
    d.arc(caja(38, 36.5, 46, 42.5), 25, 155, fill=(150, 50, 50, 255), width=int(1.0 * u))
    d.ellipse(caja(36.2, 35.6, 42.2, 38.8), fill=cafe)
    d.ellipse(caja(41.8, 35.6, 47.8, 38.8), fill=cafe)

    # sombrero de copa
    d.ellipse(caja(28.5, 22, 55.5, 27), fill=(35, 35, 45, 255))
    d.rounded_rectangle(caja(34, 9.5, 50, 25), radius=int(2 * u), fill=(35, 35, 45, 255))
    d.rectangle(caja(34, 20, 50, 23), fill=rojo)
    d.ellipse(caja(45, 19.6, 49, 23.4), fill=DORADO + (255,))

    img = img.resize((W // ss, H // ss), Image.LANCZOS)
    return pil_a_bgra(img), 14 * u / ss, 22 * u / ss


# ----------------------------------------------------------------------------
# Burbuja de diálogo del globero
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=128)
def sprite_burbuja(modo, objetivo, escala):
    ss = 2
    e = escala * ss
    w, h = int(410 * e), int(150 * e)
    pad = int(14 * e)
    W, H = w + 2 * pad, h + 2 * pad + int(28 * e)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    cola = [(pad + w * 0.72, pad + h - 2), (pad + w * 0.86, pad + h - 2), (pad + w * 0.90, pad + h + 28 * e)]
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sombra)
    ds.rounded_rectangle((pad, pad + 6 * e, pad + w, pad + h + 6 * e), 26 * e, fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(8 * e)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad, pad, pad + w, pad + h), 26 * e, fill=(255, 255, 255, 250),
                        outline=TINTA + (255,), width=int(4 * e))
    d.polygon(cola, fill=(255, 255, 255, 250), outline=TINTA + (255,))
    d.line([cola[0], cola[2], cola[1]], fill=TINTA + (255,), width=int(4 * e))
    d.line([(cola[0][0] + 3 * e, cola[0][1]), (cola[1][0] - 3 * e, cola[1][1])], fill=(255, 255, 255, 255),
           width=int(5 * e))

    d.text((pad + 24 * e, pad + 16 * e), "¡Dame un globo!", font=fuente(30 * e), fill=(110, 115, 135, 255))
    fila = pad + 95 * e
    x = pad + 26 * e
    if modo == "COLORES":
        rgb = COLORES_GLOBO[objetivo]
        g, gx, gy, _ = sprite_globo(rgb, int(26 * e))
        gi = bgra_a_pil(g)
        img.alpha_composite(gi, (int(x), int(fila - gy)))
        tx = x + gi.width + 14 * e
        tam = _tam_que_cabe(objetivo, 56 * e, pad + w - 20 * e - tx)
        d.text((tx, fila), objetivo, font=fuente(tam), anchor="lm",
               fill=tuple(rgb) + (255,), stroke_width=int(2.5 * e), stroke_fill=TINTA + (255,))
    elif modo == "FORMAS":
        dibujar_forma(d, objetivo, (x + 30 * e, fila), 28 * e, (70, 110, 240, 255), TINTA + (255,), 3 * e)
        tam = _tam_que_cabe(objetivo, 52 * e, pad + w - 20 * e - (x + 80 * e))
        d.text((x + 80 * e, fila), objetivo, font=fuente(tam), anchor="lm", fill=TINTA + (255,))
    else:
        d.text((x, fila), "con la letra", font=fuente(40 * e), anchor="lm", fill=TINTA + (255,))
        cx = x + fuente(40 * e).getlength("con la letra") + 62 * e
        d.ellipse((cx - 44 * e, fila - 44 * e, cx + 44 * e, fila + 44 * e), fill=(70, 110, 240, 255))
        d.text((cx, fila), objetivo, font=fuente(64 * e), anchor="mm", fill=(255, 255, 255, 255))

    img = img.resize((W // ss, H // ss), Image.LANCZOS)
    return pil_a_bgra(img)


def _tam_que_cabe(texto, tam, ancho):
    """Reduce el tamaño de letra hasta que el texto quepa en el ancho disponible."""
    while tam > 12 and fuente(tam).getlength(texto) > ancho:
        tam -= 2
    return tam


def texto_recortado(texto, tam, ancho):
    """Acorta una etiqueta a la anchura indicada sin modificar el dato original."""
    medir = fuente(tam).getlength
    if medir(texto) <= ancho:
        return texto
    while texto and medir(texto + "...") > ancho:
        texto = texto[:-1]
    return texto + "..."


# ----------------------------------------------------------------------------
# Título y tarjetas del menú
# ----------------------------------------------------------------------------
@functools.lru_cache(maxsize=4)
def sprite_titulo(texto, tam):
    f = fuente(tam)
    borde = max(3, tam // 11)
    paleta = list(COLORES_GLOBO.values())
    ancho = int(sum(f.getlength(c) for c in texto) + 4 * borde + tam * 0.3)
    alto = int(tam * 1.6)
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    sombra = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    x = 2 * borde
    pos = []
    for i, c in enumerate(texto):
        pos.append((x, c, paleta[i % len(paleta)]))
        x += f.getlength(c)
    ds = ImageDraw.Draw(sombra)
    for x, c, _ in pos:
        ds.text((x, tam * 0.25 + tam * 0.08), c, font=f, fill=(0, 0, 0, 160), stroke_width=borde,
                stroke_fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(tam * 0.05)))
    d = ImageDraw.Draw(img)
    for x, c, col in pos:
        if c != " ":
            d.text((x, tam * 0.25), c, font=f, fill=tuple(col) + (255,), stroke_width=borde,
                   stroke_fill=(255, 255, 255, 255))
    return pil_a_bgra(img)


@functools.lru_cache(maxsize=16)
def sprite_tarjeta(modo, w, h, activa):
    ss = 2
    W, H = w * ss, h * ss
    e = H / 400
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    borde = DORADO if activa else (255, 255, 255)
    d.rounded_rectangle((0, 0, W - 1, H - 1), 34 * e, fill=(255, 255, 255, 240), outline=borde + (255,),
                        width=int((12 if activa else 5) * e))
    cy = H * 0.40
    if modo == "COLORES":
        for i, nombre in enumerate(COLORES_GLOBO):
            g, gx, gy, _ = sprite_globo(COLORES_GLOBO[nombre], int(46 * e))
            gi = bgra_a_pil(g)
            img.alpha_composite(gi, (int(W / 2 + (i - 1) * 95 * e - gx), int(cy - gy - 10 * e)))
    elif modo == "FORMAS":
        for i, forma in enumerate(FORMAS_GLOBO):
            dibujar_forma(d, forma, (W / 2 + (i - 1) * 110 * e, cy), 40 * e, COLORES_GLOBO["AZUL"] + (255,),
                          TINTA + (255,), 3 * e)
    else:
        for i, letra in enumerate(LETRAS_GLOBO):
            d.text((W / 2 + (i - 1) * 105 * e, cy), letra, font=fuente(120 * e), anchor="mm",
                   fill=COLORES_GLOBO["AZUL"] + (255,), stroke_width=int(4 * e), stroke_fill=TINTA + (255,))
    d.text((W / 2, H * 0.80), modo.capitalize(), font=fuente(62 * e), anchor="mm", fill=TINTA + (255,))
    return pil_a_bgra(img.resize((w, h), Image.LANCZOS))
