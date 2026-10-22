"""
Render de los SVG del diseño por capas, con resvg (pip install resvg-py).

Las capas son grupos `<g inkscape:groupmode="layer">` identificados por su `id`.
La capa `transparencias` no es arte: sus figuras marcan los huecos (ojos y boca) que se
recortan del alfa. La capa `referencia` es solo una ayuda para editar y nunca se exporta.
"""
import io
import xml.etree.ElementTree as ET

import numpy as np
import resvg_py
from PIL import Image

NS = {
    "svg": "http://www.w3.org/2000/svg",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "xlink": "http://www.w3.org/1999/xlink",
}
for _prefix, _uri in NS.items():
    ET.register_namespace("" if _prefix == "svg" else _prefix, _uri)

HOLES = "transparencias"
NOT_EXPORTED = {"referencia"}


def layers(root):
    key = f"{{{NS['inkscape']}}}groupmode"
    return [g for g in root.iter(f"{{{NS['svg']}}}g") if g.get(key) == "layer"]


def with_layers(svg_text, visible):
    """Copia del SVG donde solo se muestran las capas cuyo id está en `visible`."""
    root = ET.fromstring(svg_text)
    for g in layers(root):
        style = [s for s in (g.get("style") or "").split(";") if s and not s.startswith("display")]
        style.append("display:inline" if g.get("id") in visible else "display:none")
        g.set("style", ";".join(style))
    return ET.tostring(root, encoding="unicode")


def render(svg_text, size):
    """SVG → arreglo RGBA float32 (0..1) de size×size."""
    png = resvg_py.svg_to_bytes(svg_string=svg_text, width=size, height=size)
    img = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    return np.asarray(img, dtype=np.float32) / 255


def render_with_holes(svg_text, size):
    """Arte con los huecos de la capa `transparencias` recortados del alfa.
    Devuelve (rgba, huecos) con huecos en 0..1."""
    ids = {g.get("id") for g in layers(ET.fromstring(svg_text))}
    art = render(with_layers(svg_text, ids - {HOLES} - NOT_EXPORTED), size)
    holes = render(with_layers(svg_text, {HOLES}), size)[..., 3]
    art[..., 3] *= 1 - holes
    return art, holes


def to_image(rgba):
    return Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
