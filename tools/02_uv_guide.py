"""
02 — Guía UV: contornos de los rasgos dibujados sobre la plantilla.

Uso (desde la raíz del repo, después de 01_uv_template.py):
    python tools/02_uv_guide.py

Entrada: assets/face/uv_template.png (2048x2048)
Salida:  assets/face/uv_guide.png

Los contornos salen de los conjuntos oficiales de MediaPipe (ver facelib.py). Lado
izquierdo/derecho = de la persona; en la textura el izquierdo queda a la derecha.
Con ?guide=1 la página usa esta imagen como textura para revisarla en el celular.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from facelib import SIZE, Face

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "face", "uv_template.png")
OUT = os.path.join(ROOT, "assets", "face", "uv_guide.png")

LINE = 9          # grosor de los contornos (px a 2048)
DOT = 7           # radio de los puntos de cada landmark
COLORS = {
    "oval": (255, 214, 0),
    "eye_left": (0, 220, 255),
    "eye_right": (0, 255, 140),
    "brow": (170, 255, 60),
    "lips_outer": (255, 40, 120),
    "lips_inner": (255, 255, 255),
    "nose": (90, 140, 255),
    "tip": (255, 0, 0),
}


def font(size):
    return ImageFont.load_default(size=size)


def polyline(draw, pts, color, closed):
    pts = [tuple(p) for p in pts]
    if closed:
        pts.append(pts[0])
    draw.line(pts, fill=color + (255,), width=LINE, joint="curve")


def dots(draw, pts, color, r=DOT):
    for x, y in pts:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color + (255,), outline=(0, 0, 0, 255), width=2)


def label(draw, xy, text, color, size=34, anchor="mm"):
    draw.text(xy, text, font=font(size), fill=color + (255,), anchor=anchor,
              stroke_width=5, stroke_fill=(0, 0, 0, 255))


def main():
    face = Face(SIZE)
    print("[02]", face.summary())

    base = Image.open(TEMPLATE).convert("RGBA")
    if base.size != (SIZE, SIZE):
        base = base.resize((SIZE, SIZE), Image.LANCZOS)
    # Atenuar la plantilla para que los contornos destaquen.
    base.putalpha(base.getchannel("A").point(lambda a: a * 0.6))
    img = Image.new("RGBA", (SIZE, SIZE))
    img.alpha_composite(base)
    draw = ImageDraw.Draw(img)

    P = face.px
    polyline(draw, P(face.oval), COLORS["oval"], True)
    for side in ("left", "right"):
        polyline(draw, P(face.eye[side]), COLORS[f"eye_{side}"], True)
        polyline(draw, P(face.brow_upper[side]), COLORS["brow"], False)
        polyline(draw, P(face.brow_lower[side]), COLORS["brow"], False)
    polyline(draw, P(face.lips_outer), COLORS["lips_outer"], True)
    polyline(draw, P(face.lips_inner), COLORS["lips_inner"], True)
    polyline(draw, P(face.nose_bridge), COLORS["nose"], False)
    polyline(draw, P(face.nostrils), COLORS["nose"], True)

    for ids, key in ((face.oval, "oval"), (face.eye["left"], "eye_left"),
                     (face.eye["right"], "eye_right"), (face.lips_outer, "lips_outer"),
                     (face.lips_inner, "lips_inner")):
        dots(draw, P(ids), COLORS[key])
    tip = P(face.nose_tip)
    dots(draw, [tip], COLORS["tip"], r=16)

    # Etiquetas
    for side, text in (("left", "OJO IZQ. (persona)"), ("right", "OJO DER. (persona)")):
        c = P(face.eye[side])
        label(draw, (c[:, 0].mean(), c[:, 1].max() + 50), text, COLORS[f"eye_{side}"])
        b = P(face.brow_upper[side])
        label(draw, (b[:, 0].mean(), b[:, 1].min() - 40), "ceja", COLORS["brow"], 30)
    lo = P(face.lips_outer)
    label(draw, (lo[:, 0].mean(), lo[:, 1].max() + 50), "labios (ext. / int.)", COLORS["lips_outer"])
    label(draw, (tip[0] + 30, tip[1] - 10), f"punta de nariz ({face.nose_tip})", COLORS["tip"], 30, "lm")
    ov = P(face.oval)
    label(draw, (SIZE / 2, ov[:, 1].min() + 60), "contorno (FACE_OVAL)", COLORS["oval"])
    label(draw, (40, SIZE - 50),
          "Vista de frente: el lado IZQUIERDO de la persona queda a la DERECHA de la textura",
          (255, 255, 255), 34, "lm")

    img.save(OUT, optimize=True)
    print(f"[02] listo: {OUT}")


if __name__ == "__main__":
    main()
