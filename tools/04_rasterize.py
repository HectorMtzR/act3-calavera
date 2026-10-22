"""
04 — Rasterizado: SVG del diseño → PNG 2048x2048 con alfa, borde suave y padding.

Uso (desde la raíz del repo, después de 03_generate_svg.py o de retocar los SVG a mano):
    python tools/04_rasterize.py

Entradas: design/calavera.svg, design/calavera_alt.svg
Salidas:  assets/mask/calavera.png, assets/mask/calavera_alt.png
          docs/textura/04_textura.png (vista previa sobre cuadrícula, para el README)

Pasos:
1. Render con resvg; la capa `transparencias` se recorta del alfa (huecos de ojos y boca).
2. Borde suave: el alfa baja a 0 en los últimos FEATHER px del contorno de la malla.
3. Padding: los píxeles transparentes toman el color de los opacos más cercanos, para que
   el filtrado y los mipmaps no mezclen colores ajenos en los bordes y en los huecos.
"""
import os
import sys

import numpy as np
from PIL import Image

import svglib
from facelib import SIZE
from uvlib import blur, fill_triangles, load_canonical_obj

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = ["calavera", "calavera_alt"]
FEATHER = 20          # px (a 2048) de desvanecido en el contorno de la cara
PAD_EXACT = 12        # px de padding por vecino más cercano; el resto, por promedio de bloques
MAX_MB = 3.0


def island_mask(size):
    """Píxeles cubiertos por los triángulos de la malla (fila 0 arriba, como la imagen)."""
    _, uvs, tri = load_canonical_obj()
    return fill_triangles(size, uvs[tri])[::-1]


def soft_edge(island, radius):
    """1 dentro de la isla, bajando suavemente a 0 en el contorno exterior."""
    b = blur(island.astype(np.float32), radius / 2, passes=3)
    t = np.clip((b - 0.5) * 2, 0, 1)
    return t * t * (3 - 2 * t)


def dilate_colors(rgb, known, steps):
    """Extiende los colores hacia los píxeles vacíos, un píxel por paso (vecinos de 8)."""
    rgb, known = rgb.copy(), known.copy()
    for _ in range(steps):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(known.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    k = np.roll(np.roll(known, dy, 0), dx, 1)
                    acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * k[..., None]
                    cnt += k
        new = ~known & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        known |= new
    return rgb, known


def pull_push(rgb, known):
    """Rellena todo lo desconocido con el promedio de bloques cada vez más grandes."""
    if known.all() or rgb.shape[0] == 1:
        return rgb
    n = rgb.shape[0] // 2
    w = known.astype(np.float32).reshape(n, 2, n, 2).sum((1, 3))
    c = (rgb * known[..., None]).reshape(n, 2, n, 2, 3).sum((1, 3))
    small = pull_push(c / np.maximum(w, 1e-6)[..., None], w > 0)
    up = small.repeat(2, 0).repeat(2, 1)
    return np.where(known[..., None], rgb, up)


def rasterize(svg_path, island, edge):
    rgba, holes = svglib.render_with_holes(open(svg_path, encoding="utf-8").read(), SIZE)
    alpha = rgba[..., 3] * edge
    known = rgba[..., 3] > 0.02
    rgb, known = dilate_colors(rgba[..., :3], known, PAD_EXACT)
    rgb = pull_push(rgb, known)
    return np.dstack([rgb, alpha]), holes


def check(rgba, island, holes, name):
    a = rgba[..., 3]
    inner = island & (soft_edge(island, FEATHER * 2) > 0.999) & (holes < 0.01)
    gaps = int((a[inner] < 0.99).sum())
    print(f"[04] {name}: huecos {int((holes > 0.5).sum())} px; "
          f"píxeles semitransparentes dentro de la cara: {gaps}")
    if gaps > 200:
        print("[04] ADVERTENCIA: la base no cubre toda la isla UV")


def preview(rgba_list, out, size=1024):
    tiles = []
    yy, xx = np.mgrid[0:size, 0:size]
    checker = np.where(((yy // 32) + (xx // 32)) % 2, 0.55, 0.42)[..., None].repeat(3, 2)
    for rgba in rgba_list:
        img = np.asarray(Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")
                         .resize((size, size), Image.LANCZOS), np.float32) / 255
        a = img[..., 3:]
        tiles.append(img[..., :3] * a + checker * (1 - a))
    sheet = np.concatenate(tiles, axis=1)
    Image.fromarray((sheet * 255 + 0.5).astype(np.uint8)).save(out, optimize=True)


def main():
    island = island_mask(SIZE)
    edge = soft_edge(island, FEATHER)
    os.makedirs(os.path.join(ROOT, "assets", "mask"), exist_ok=True)
    results = []
    for name in NAMES:
        svg = os.path.join(ROOT, "design", f"{name}.svg")
        rgba, holes = rasterize(svg, island, edge)
        check(rgba, island, holes, name)
        out = os.path.join(ROOT, "assets", "mask", f"{name}.png")
        Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(out, optimize=True)
        mb = os.path.getsize(out) / 2 ** 20
        print(f"[04] {out} ({mb:.2f} MB)")
        if mb > MAX_MB:
            print(f"[04] ADVERTENCIA: pesa más de {MAX_MB} MB")
        results.append(rgba)
    out = os.path.join(ROOT, "docs", "textura", "04_textura.png")
    preview(results, out)
    print(f"[04] vista previa: {out}")


if __name__ == "__main__":
    sys.exit(main())
