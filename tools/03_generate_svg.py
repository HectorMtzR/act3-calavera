"""
03 — Diseño de la calavera como SVG anclado a los landmarks, en espacio UV (2048x2048).

Uso (desde la raíz del repo):
    python tools/03_generate_svg.py

Salidas:
    design/calavera.svg, design/calavera_alt.svg   (misma geometría, distinta paleta)
    docs/textura/03_diseno.png                     (vista previa de ambas paletas)

Cada elemento se posiciona y escala a partir de los contornos de su zona (facelib.py).
Las medidas están en "anchos de ojo" (EW), así el diseño sigue las proporciones de la malla.
Simetría: los elementos se construyen con los landmarks del lado DERECHO de la persona y
el lado izquierdo usa sus pares reflejados (Face.mirror).

Capas (grupos con nombre, editables en Inkscape / Figma / Illustrator):
    base, huesos (sombreado), craneo (silueta y líneas óseas), frente, mejillas, menton, nariz, boca, ojos, transparencias, referencia
`transparencias` marca en magenta los huecos exactos de ojos y boca: 04_rasterize.py los
recorta del alfa. `referencia` (oculta) muestra la guía UV para retocar a mano.
"""
import math
import os

import numpy as np
from PIL import Image

import svglib
from facelib import SIZE, Face

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN_DIR = os.path.join(ROOT, "design")
PREVIEW = os.path.join(ROOT, "docs", "textura", "03_diseno.png")

# ---------- Paletas ----------
BONE = "#f4efe6"
INK = "#1b1b1b"
HOLE = "#ff00ff"  # marcador de la capa transparencias (no es color de la textura)
BONE_EDGE = "#dcd1bf"   # hueso hacia los bordes (degradado de la base)
SHADOW = "#7d7264"      # sombras de la capa huesos
TOOTH = "#fbf8f1"       # dientes (más claros que el hueso para que destaquen)
HOLLOW = "#2b2520"      # hundimiento fuera de la mandíbula
LEAF = ("#2f8f3a", "#7cc242")   # hojas (oscura, clara)
VINE = "#2f7d32"

PALETTES = {
    "calavera": {
        "petal_a": "#ff8c00", "petal_b": "#ffb703", "flower_center": "#c2410c",
        "picado_a": "#e4007c", "picado_b": "#7b2cbf",
        "scroll": "#00a6a6", "dots": "#e4007c", "chin": "#7b2cbf",
    },
    # Mismo diseño; cambian los acentos. Base y zonas negras iguales.
    "calavera_alt": {
        "petal_a": "#7b2cbf", "petal_b": "#e4007c", "flower_center": "#d4a017",
        "picado_a": "#ff8c00", "picado_b": "#ffb703",
        "scroll": "#d4a017", "dots": "#d4a017", "chin": "#d4a017",
    },
}

# ---------- Proporciones (en anchos de ojo, EW) ----------
OUTLINE = 0.016          # contorno de pétalos y flores
SOCKET = {"offset": 0.16, "stretch": 1.55, "lift": 0.08}  # contorno del ojo agrandado, estirado y subido
EYE_PETALS = {"count": 18, "length": 0.30, "width": 0.11, "inner_len": 0.70,
              "overlap": 0.05, "skip_inner": 0.45}
FLOWER = {"radius": 0.42, "rise": 0.14}            # rise: altura entre ceja y óvalo (0..1)
PICADO = {"inset": 0.20, "cut": 0.42, "width": 0.36, "height": 0.34, "gap": 0.06,
          "string": 0.022}
MOUTH = {"line": 0.045, "teeth": 9, "tooth_ext": 0.13, "ext_len": 0.55, "ext_rise": 0.10,
         "ext_ticks": 3, "teeth_ext": 0.07}
CHEEK = {"out": 0.68, "spiral": 0.27, "turns": 1.55, "stroke": 0.058, "dot": 0.072}
CHIN = {"at": 0.47, "petal": 0.22, "curl": 0.14, "stroke": 0.048}
NOSE = {"width": 0.92, "drop": 0.04}
# Sombreado óseo: (desenfoque en EW, opacidad). "teeth": dientes color hueso sobre los
# labios (más calavera); False = labios oscuros.
BONES = {"orbit": 0.16, "orbit_shade": (0.10, 0.55), "temple_shade": (0.12, 0.15),
         "nose_shade": (0.07, 0.45), "chin_shade": (0.07, 0.28), "teeth": True}
# Estructura del cráneo (en EW): silueta con pómulo saliente, muesca y mandíbula más
# angosta que la cara; "*_in" = cuánto entra la silueta desde el contorno de la cara.
SKULL = {"outline": (0.01, 0.065, 0.05), "temple_in": 0.55, "cheek_in": 0.62, "jaw_in": 1.05,
         "chin_in": 0.30, "hollow_opacity": 0.5, "line": (0.055, 0.008),
         "zygo_len": 0.55, "maxilla_len": 0.62}
TEETH = {"count": 8, "ext": 0.16, "gap": 0.035}
VINES = {"leaves": 0.75, "leaf_w": 0.32, "stroke": 0.03}


# ---------- Geometría ----------
def catmull(pts, closed=True, n=12):
    """Curva Catmull-Rom muestreada densamente."""
    P = np.asarray(pts, float)
    k = len(P)
    idx = (lambda i: P[i % k]) if closed else (lambda i: P[min(max(i, 0), k - 1)])
    out = []
    for i in range(k if closed else k - 1):
        p0, p1, p2, p3 = idx(i - 1), idx(i), idx(i + 1), idx(i + 2)
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    if not closed:
        out.append(P[-1])
    return np.array(out)


def resample(poly, n, closed=True):
    P = np.asarray(poly, float)
    Q = np.vstack([P, P[:1]]) if closed else P
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n, endpoint=not closed)
    return np.stack([np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])], axis=1)


def normals(poly, closed=True, toward=None):
    """Normales unitarias. Cerrado: hacia afuera. Abierto: hacia el punto `toward`."""
    P = np.asarray(poly, float)
    if closed:
        t = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    else:
        t = np.gradient(P, axis=0)
    n = np.stack([t[:, 1], -t[:, 0]], axis=1)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    ref = P - P.mean(0) if toward is None else np.asarray(toward) - P
    sign = 1 if np.sum(n * ref) > 0 else -1
    return n * (sign if toward is not None else sign)


def f(p):
    return f"{p[0]:.1f},{p[1]:.1f}"


def bezier_d(pts, closed=True):
    """Trayectoria SVG suave (Catmull-Rom → Bézier cúbica) que pasa por los puntos."""
    P = np.asarray(pts, float)
    k = len(P)
    idx = (lambda i: P[i % k]) if closed else (lambda i: P[min(max(i, 0), k - 1)])
    d = [f"M{f(P[0])}"]
    for i in range(k if closed else k - 1):
        p0, p1, p2, p3 = idx(i - 1), idx(i), idx(i + 1), idx(i + 2)
        d.append(f"C{f(p1 + (p2 - p0) / 6)} {f(p2 - (p3 - p1) / 6)} {f(p2)}")
    return "".join(d) + ("Z" if closed else "")


def poly_d(pts):
    return "M" + "L".join(f(p) for p in pts) + "Z"


def circle_d(c, r):
    x, y = c
    return f"M{x - r:.1f},{y:.1f}a{r:.1f},{r:.1f} 0 1,0 {2 * r:.1f},0a{r:.1f},{r:.1f} 0 1,0 {-2 * r:.1f},0Z"


def place(x, y, angle_rad, sx=1):
    """Transformación SVG: mover a (x, y), girar y (opcional) reflejar en x local."""
    t = f"translate({x:.1f},{y:.1f}) rotate({math.degrees(angle_rad):.2f})"
    return t + (" scale(-1,1)" if sx < 0 else "")


def lerp(a, b, t):
    return np.asarray(a, float) + (np.asarray(b, float) - np.asarray(a, float)) * t


# ---------- Formas base (coordenadas locales, apuntando a +x) ----------
def petal_d(length, width):
    """Pétalo de cempasúchil: base angosta en el origen y punta con tres ondas."""
    L, W = length, width
    pts = [
        f"M0,{-0.35 * W:.1f}",
        f"C{0.35 * L:.1f},{-1.05 * W:.1f} {0.70 * L:.1f},{-1.10 * W:.1f} {0.86 * L:.1f},{-0.80 * W:.1f}",
        f"Q{1.02 * L:.1f},{-0.62 * W:.1f} {0.95 * L:.1f},{-0.25 * W:.1f}",
        f"Q{1.06 * L:.1f},0 {0.95 * L:.1f},{0.25 * W:.1f}",
        f"Q{1.02 * L:.1f},{0.62 * W:.1f} {0.86 * L:.1f},{0.80 * W:.1f}",
        f"C{0.70 * L:.1f},{1.10 * W:.1f} {0.35 * L:.1f},{1.05 * W:.1f} 0,{0.35 * W:.1f}",
        "Z",
    ]
    return "".join(pts)


def ruffled_ring_petal(r0, r1, half_angle):
    """Pétalo en abanico para la flor de la frente (polar, centrado en el ángulo 0)."""
    def pol(r, a):
        return (r * math.cos(a), r * math.sin(a))
    a = half_angle
    d = [f"M{f(pol(r0, -a * 0.45))}", f"L{f(pol(r1 * 0.88, -a))}"]
    steps = 3
    for k in range(steps):
        a0 = -a + 2 * a * k / steps
        a1 = -a + 2 * a * (k + 1) / steps
        d.append(f"Q{f(pol(r1 * 1.08, (a0 + a1) / 2))} {f(pol(r1 * (0.88 if k == steps - 1 else 0.94), a1))}")
    d.append(f"L{f(pol(r0, a * 0.45))}Z")
    return "".join(d)


def leaf_d(length, width):
    """Hoja apuntando a +x con la base en el origen."""
    L, W = length, width
    return (f"M0,0C{0.30 * L:.1f},{-W:.1f} {0.72 * L:.1f},{-0.9 * W:.1f} {L:.1f},0"
            f"C{0.72 * L:.1f},{0.9 * W:.1f} {0.30 * L:.1f},{W:.1f} 0,0Z")


def profile(n, w0, wm, w1):
    """Anchos a lo largo de un trazo: w0 al inicio, wm a la mitad, w1 al final."""
    t = np.linspace(0, 1, n)
    return w0 + (w1 - w0) * t + (wm - (w0 + w1) / 2) * 4 * t * (1 - t)


def tapered_d(pts, widths):
    """Trazo relleno de ancho variable (como pincel): se adelgaza donde `widths` es chico."""
    P = np.asarray(pts, float)
    w = np.asarray(widths, float)[:, None] / 2
    t = np.gradient(P, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    perp = np.stack([-t[:, 1], t[:, 0]], axis=1)
    return bezier_d(np.vstack([P + perp * w, (P - perp * w)[::-1]]))


def spiral_pts(center, r0, r1, a0, turns, sx, n=90):
    """Espiral de Arquímedes; sx = -1 la refleja para el lado opuesto."""
    s = np.linspace(0, 1, n)
    r = r0 + (r1 - r0) * s
    a = a0 + 2 * math.pi * turns * s
    return np.stack([center[0] + sx * r * np.cos(a), center[1] + r * np.sin(a)], axis=1)


# ---------- Documento ----------
class Svg:
    def __init__(self):
        self.layers = {}
        self.defs = {}

    def blur(self, std):
        """Id de un filtro de desenfoque gaussiano (se declara una vez en <defs>)."""
        fid = f"desenfoque-{int(round(std))}"
        self.defs[fid] = (f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%">'
                          f'<feGaussianBlur stdDeviation="{std:.1f}"/></filter>')
        return fid

    def add(self, layer, element):
        self.layers.setdefault(layer, []).append(element)

    def path(self, layer, d, fill="none", stroke=None, width=None, extra=""):
        s = f'<path d="{d}" fill="{fill}"'
        if stroke:
            s += f' stroke="{stroke}" stroke-width="{width:.1f}" stroke-linecap="round" stroke-linejoin="round"'
        self.add(layer, s + (f" {extra}" if extra else "") + "/>")

    def text(self, order, title):
        out = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="{svglib.NS["svg"]}" xmlns:xlink="{svglib.NS["xlink"]}"',
            f'     xmlns:inkscape="{svglib.NS["inkscape"]}" xmlns:sodipodi="{svglib.NS["sodipodi"]}"',
            f'     width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">',
            f"  <title>{title}</title>",
            "  <!-- Generado por tools/03_generate_svg.py en espacio UV de la malla canónica de",
            "       MediaPipe. Se puede retocar a mano; 04_rasterize.py lo convierte a PNG.",
            "       Capa transparencias: lo magenta se vuelve hueco (ojos y boca).",
            "       Capa referencia: guía UV oculta, solo para editar; no se exporta. -->",
        ]
        if self.defs:
            out += ["  <defs>"] + [f"    {d}" for d in self.defs.values()] + ["  </defs>"]
        for name in order:
            extra = ""
            if name == "referencia":
                extra = ' style="display:none" sodipodi:insensitive="true"'
            out.append(f'  <g id="{name}" inkscape:groupmode="layer" inkscape:label="{name}"{extra}>')
            out += [f"    {e}" for e in self.layers.get(name, [])]
            out.append("  </g>")
        out.append("</svg>")
        return "\n".join(out) + "\n"


class Side:
    """Un lado de la cara. Los elementos se definen con índices del lado derecho de la
    persona; el izquierdo los convierte con el mapa de pares reflejados."""

    def __init__(self, face, name):
        self.face = face
        self.name = name
        self.sx = -1 if name == "right" else 1  # dirección "hacia afuera" en x de imagen

    def ids(self, idx):
        idx = np.asarray(idx)
        return idx if self.name == "right" else self.face.mirror[idx]

    def P(self, idx):
        return self.face.px(self.ids(idx))


# ---------- Elementos ----------
class Design:
    def __init__(self, face):
        self.face = face
        self.sides = [Side(face, "right"), Side(face, "left")]
        eye = face.px(face.eye["right"])
        self.EW = float(eye[:, 0].max() - eye[:, 0].min())  # ancho del ojo en px
        # El lado izquierdo reflejado debe coincidir con el contorno oficial del ojo izquierdo.
        assert set(face.mirror[face.eye["right"]]) == set(face.eye["left"])
        assert set(face.mirror[face.brow_upper["right"]]) == set(face.brow_upper["left"])

        P = face.px
        self.oval = catmull(P(face.oval), True, 16)
        self.cx = float(P(face.nose_bridge)[:, 0].mean())   # eje de simetría
        self._skull = {}
        lips = P(face.lips_outer)
        self.mouth_corner = {
            "right": face.lips_outer[int(lips[:, 0].argmin())],
            "left": face.lips_outer[int(lips[:, 0].argmax())],
        }

    def build(self, pal):
        svg = Svg()
        self.base(svg)
        self.bones(svg)
        self.skull(svg)
        self.forehead(svg, pal)
        for side in self.sides:
            self.cheek(svg, pal, side)
        self.chin(svg, pal)
        self.nose(svg)
        self.mouth(svg)
        for side in self.sides:
            self.eye(svg, pal, side)
        self.holes(svg)
        svg.add("referencia", f'<image xlink:href="../assets/face/uv_guide.png" x="0" y="0" '
                              f'width="{SIZE}" height="{SIZE}" opacity="0.6"/>')
        return svg

    # base: blanco hueso en todo el contorno de la cara
    def base(self, svg):
        c = self.face.px(self.face.nose_tip)
        r = np.linalg.norm(self.oval - c, axis=1).max()
        svg.defs["degradado-hueso"] = (
            f'<radialGradient id="degradado-hueso" gradientUnits="userSpaceOnUse" cx="{c[0]:.1f}" '
            f'cy="{c[1]:.1f}" r="{r:.1f}"><stop offset="0.55" stop-color="{BONE}"/>'
            f'<stop offset="1" stop-color="{BONE_EDGE}"/></radialGradient>')
        svg.path("base", bezier_d(resample(self.oval, 72)), fill="url(#degradado-hueso)", extra='id="hueso"')

    def oval_arc(self, keep):
        """Tramo contiguo del óvalo donde `keep` es verdadero, en orden a lo largo de la curva."""
        start = int(np.argmax(~keep))
        idx = np.roll(np.arange(len(self.oval)), -start)
        return self.oval[idx][keep[idx]]

    def oval_at(self, side, y):
        """Punto del óvalo de ese lado con la altura más cercana a y."""
        o = self.oval[(self.oval[:, 0] - SIZE / 2) * side.sx > 0]
        return o[np.argmin(np.abs(o[:, 1] - y))]

    # huesos: sombras suaves y líneas que dan volumen de cráneo
    def bones(self, svg):
        face, EW, B = self.face, self.EW, BONES
        P = face.px

        def shade(d, key, name):
            blur, opacity = B[key]
            svg.path("huesos", d, fill=SHADOW, extra=f'id="{name}" opacity="{opacity}" '
                                                     f'filter="url(#{svg.blur(blur * EW)})"')

        def line(pts, name):
            svg.path("huesos", bezier_d(resample(catmull(pts, False, 12), 10, closed=False), closed=False),
                     stroke=SHADOW, width=B["line"] * EW, extra=f'id="{name}" opacity="{B["line_opacity"]}"')

        def ellipse_d(c, rx, ry):
            return (f"M{c[0] - rx:.1f},{c[1]:.1f}a{rx:.1f},{ry:.1f} 0 1,0 {2 * rx:.1f},0"
                    f"a{rx:.1f},{ry:.1f} 0 1,0 {-2 * rx:.1f},0Z")

        lips = P(face.lips_outer)
        for side in self.sides:
            n = side.name
            ey = np.array([0.0, EW])        # hacia abajo
            sock = self.socket(side)
            # Órbita: sombra alrededor de la cuenca.
            shade(bezier_d(resample(sock + normals(sock) * B["orbit"] * EW, 32)), "orbit_shade", f"orbita-{n}")

            # Sien: hundimiento junto al extremo de la ceja.
            brow_out = side.P(face.brow_upper["right"])[-1]
            c = lerp(brow_out, self.oval_at(side, brow_out[1]), 0.55) - 0.1 * ey
            shade(ellipse_d(c, 0.30 * EW, 0.55 * EW), "temple_shade", f"sien-{n}")

        # Cavidad nasal: sombra alrededor del corazón.
        shade(self.heart_d(1.3), "nose_shade", "cavidad-nasal")
        # Mentón: sombra bajo el labio inferior.
        c = np.array([lips[:, 0].mean(), lips[:, 1].max() + 0.20 * EW])
        shade(ellipse_d(c, 0.45 * EW, 0.12 * EW), "chin_shade", "menton-sombra")

    # cráneo: silueta con pómulo saliente, muesca y mandíbula más angosta, hundimiento fuera
    # de la mandíbula y líneas del cigomático y del maxilar
    def skull_points(self, side):
        """Puntos clave de la silueta de ese lado (px), anclados al óvalo, la cuenca, la
        ceja, la nariz y la boca."""
        if side.name in self._skull:
            return self._skull[side.name]
        face, EW, K = self.face, self.EW, SKULL
        P = face.px
        sx = side.sx
        on = normals(self.oval)                                   # hacia afuera de la cara
        mine = (self.oval[:, 0] - self.cx) * sx >= -1

        def inset_at(y, d):
            i = np.where(mine)[0][np.argmin(np.abs(self.oval[mine, 1] - y))]
            return self.oval[i] - on[i] * d * EW

        sock = self.socket(side)
        brow_out = side.P(face.brow_upper["right"])[-1]
        y_notch = P(face.nostrils)[:, 1].max() + 0.05 * EW        # muesca a la altura de la base de la nariz
        top = inset_at(lerp(self.oval[:, 1].min(), brow_out[1], 0.35), 0.12)   # arranca pegada al borde
        temple = inset_at(brow_out[1], K["temple_in"])
        cheek = inset_at(sock[:, 1].max() + 0.25 * EW, K["cheek_in"])
        cheek_low = inset_at(y_notch - 0.18 * EW, K["cheek_in"])

        # Mandíbula: el óvalo hacia adentro, de jaw_in en la muesca a chin_in en el mentón.
        idx = np.where(mine & (self.oval[:, 1] >= y_notch))[0]
        idx = idx[np.argsort(self.oval[idx, 1])]
        y_bot = self.oval[:, 1].max()
        t = (self.oval[idx, 1] - y_notch) / (y_bot - y_notch)
        inset = (K["jaw_in"] + (K["chin_in"] - K["jaw_in"]) * t ** 0.6) * EW
        jaw = self.oval[idx] - on[idx] * inset[:, None]
        jaw = np.vstack([resample(jaw, 8, closed=False), [[self.cx, y_bot - K["chin_in"] * EW]]])

        outline = resample(catmull(np.vstack([[top, temple, cheek, cheek_low], jaw]), False, 10), 80, closed=False)
        notch = jaw[0]
        mouth = side.P(self.mouth_corner["right"])
        under_eye = sock[np.argmax(sock[:, 1])] + np.array([0.0, 0.15 * EW])
        self._skull[side.name] = pts = {
            "outline": outline, "notch": notch, "cheek": cheek, "cheek_low": cheek_low,
            "under_eye": under_eye, "mouth": mouth, "y_notch": y_notch,
        }
        return pts

    def skull(self, svg):
        EW, K = self.EW, SKULL
        for side in self.sides:
            sx, n = side.sx, side.name
            S = self.skull_points(side)
            outline = S["outline"]

            # Fuera del cráneo: entre la silueta y el borde de la cara (hasta fuera de la isla).
            inner = outline
            mine = ((self.oval[:, 0] - self.cx) * sx >= -1) & (self.oval[:, 1] >= outline[0, 1])
            outer = self.oval[mine]
            outer = outer[np.argsort(outer[:, 1])] + normals(self.oval)[mine][np.argsort(outer[:, 1])] * 0.3 * EW
            svg.path("craneo", poly_d(np.vstack([inner, outer[::-1]])), fill=HOLLOW,
                     extra=f'id="hundimiento-{n}" opacity="{K["hollow_opacity"]}"')

            w0, wm, w1 = K["outline"]
            svg.path("craneo", tapered_d(outline, profile(len(outline), w0 * EW, wm * EW, w1 * EW)),
                     fill=INK, extra=f'id="silueta-{n}"')

            # Cigomático: de la muesca hacia abajo del ojo. Maxilar: de la muesca a la comisura.
            a, b = K["line"]
            for name, target, frac, bend in (
                    ("cigomatico", S["under_eye"], K["zygo_len"], np.array([0.0, 0.10 * EW])),
                    ("maxilar", S["mouth"] + np.array([sx * 0.08 * EW, 0.0]), K["maxilla_len"],
                     np.array([sx * 0.06 * EW, -0.06 * EW]))):
                end = lerp(S["notch"], target, frac)
                curve = resample(catmull([S["notch"], lerp(S["notch"], end, 0.5) + bend, end], False, 16),
                                 30, closed=False)
                svg.path("craneo", tapered_d(curve, profile(30, a * EW, a * 0.8 * EW, b * EW)),
                         fill=INK, extra=f'id="{name}-{n}"')

    # ojos: cuenca negra que sigue el contorno del ojo + anillo de pétalos
    def socket(self, side):
        """Contorno del ojo desplazado hacia afuera (redondea las comisuras), estirado en
        vertical alrededor de su centro y subido un poco hacia la ceja."""
        eye = catmull(side.P(self.face.eye["right"]), True, 12)
        ring = eye + normals(eye) * SOCKET["offset"] * self.EW
        c = eye.mean(0)
        ring[:, 1] = c[1] + (ring[:, 1] - c[1]) * SOCKET["stretch"] - SOCKET["lift"] * self.EW
        return resample(catmull(resample(ring, 24), True, 8), 48)

    def eye(self, svg, pal, side):
        EW = self.EW
        sock = self.socket(side)
        cfg = EYE_PETALS
        ring = resample(sock, cfg["count"] * 2)
        nrm = normals(ring)
        inward = np.array([-side.sx, 0.0])
        g = [f'<g id="petalos-{side.name}" stroke="{INK}" stroke-width="{OUTLINE * EW:.1f}" stroke-linejoin="round">']
        front = []
        for i, (p, n) in enumerate(zip(ring, nrm)):
            if n @ inward > cfg["skip_inner"]:
                continue
            ang = math.atan2(n[1], n[0])
            base = p - n * cfg["overlap"] * EW
            if i % 2 == 0:   # fila de atrás: pétalos largos
                d = petal_d(cfg["length"] * EW, cfg["width"] * EW)
                g.append(f'  <path d="{d}" fill="{pal["petal_a"]}" transform="{place(*base, ang)}"/>')
            else:            # fila de adelante, entre los anteriores
                d = petal_d(cfg["length"] * cfg["inner_len"] * EW, cfg["width"] * 0.85 * EW)
                front.append(f'  <path d="{d}" fill="{pal["petal_b"]}" transform="{place(*base, ang)}"/>')
        svg.add("ojos", "\n    ".join(g + front + ["</g>"]))
        svg.path("ojos", bezier_d(sock), fill=INK, extra=f'id="cuenca-{side.name}"')

    # nariz: corazón invertido (punta arriba) sobre la punta y las aletas
    def nose(self, svg):
        svg.path("nariz", self.heart_d(), fill=INK, extra='id="corazon"')

    def heart_d(self, scale=1.0):
        """Corazón invertido; `scale` lo agranda alrededor de su centro."""
        face, P = self.face, self.face.px
        nos = P(face.nostrils)
        bridge = face.nose_bridge
        top = P(bridge[bridge.index(face.nose_tip) - 1])
        cx = top[0]
        W = (nos[:, 0].max() - nos[:, 0].min()) / 2 * NOSE["width"]
        y0, y1 = top[1], nos[:, 1].max() + NOSE["drop"] * self.EW
        H = y1 - y0

        cy = y0 + 0.6 * H
        W, H = W * scale, H * scale
        y0 = cy - 0.6 * H

        def q(x, y):
            return f"{cx + x * W:.1f},{y0 + y * H:.1f}"
        d = (f"M{q(0, 0)}"
             f"C{q(-0.35, 0.28)} {q(-1, 0.42)} {q(-1, 0.70)}"
             f"C{q(-1, 0.94)} {q(-0.76, 1.02)} {q(-0.50, 1.0)}"
             f"C{q(-0.26, 0.98)} {q(-0.08, 0.90)} {q(0, 0.80)}"
             f"C{q(0.08, 0.90)} {q(0.26, 0.98)} {q(0.50, 1.0)}"
             f"C{q(0.76, 1.02)} {q(1, 0.94)} {q(1, 0.70)}"
             f"C{q(1, 0.42)} {q(0.35, 0.28)} {q(0, 0)}Z")
        return d

    # boca: dientes sobre los labios (o labios oscuros), línea extendida a las mejillas
    # y separaciones verticales
    def mouth(self, svg):
        face, EW = self.face, self.EW
        P = face.px
        outer = P(face.lips_outer)
        if BONES["teeth"]:
            return self.teeth(svg)
        svg.path("boca", bezier_d(outer), fill=INK, extra='id="labios"')

        # Contorno exterior partido en labio superior e inferior (de comisura a comisura).
        loop = list(face.lips_outer)
        i0, i1 = loop.index(self.mouth_corner["right"]), loop.index(self.mouth_corner["left"])
        a = P(loop[i0:i1 + 1] if i0 < i1 else loop[i0:] + loop[:i1 + 1])
        b = P(loop[i1:] + loop[:i0 + 1] if i0 < i1 else loop[i1:i0 + 1])
        upper, lower = (a, b) if a[:, 1].mean() < b[:, 1].mean() else (b, a)
        upper, lower = upper[np.argsort(upper[:, 0])], lower[np.argsort(lower[:, 0])]
        x0, x1 = outer[:, 0].min(), outer[:, 0].max()
        width = MOUTH["line"] * EW
        ext = MOUTH["tooth_ext"] * EW
        teeth = []
        for t in np.linspace(0, 1, MOUTH["teeth"] + 2)[1:-1]:
            x = x0 + (x1 - x0) * t
            yt, yb = np.interp(x, upper[:, 0], upper[:, 1]), np.interp(x, lower[:, 0], lower[:, 1])
            fade = 1 - 0.35 * abs(t - 0.5) * 2   # más cortos hacia las comisuras
            teeth.append(f"M{x:.1f},{yt - ext * fade:.1f}L{x:.1f},{yb + ext * fade:.1f}")

        # Línea desde cada comisura hacia la mejilla, curvada hacia arriba, con marcas.
        for side in self.sides:
            c = P(side.ids(self.mouth_corner["right"]))
            L = MOUTH["ext_len"] * EW
            end = c + np.array([side.sx * L, -MOUTH["ext_rise"] * EW])
            mid = c + np.array([side.sx * L * 0.55, -MOUTH["ext_rise"] * EW * 0.15])
            curve = catmull([c, mid, end], closed=False, n=20)
            svg.path("boca", bezier_d(resample(curve, 8, closed=False), closed=False),
                     stroke=INK, width=width, extra=f'id="sonrisa-{side.name}"')
            nrm = normals(curve, closed=False, toward=curve[0] + [0, -1e4])
            for k in range(1, MOUTH["ext_ticks"] + 1):
                s = k / (MOUTH["ext_ticks"] + 0.6)
                i = int(s * (len(curve) - 1))
                h = ext * (1 - 0.45 * s) * 0.9
                p, n = curve[i], nrm[i]
                teeth.append(f"M{f(p + n * h)}L{f(p - n * h)}")
        svg.path("boca", "".join(teeth), stroke=INK, width=width, extra='id="dientes"')

    def lip_curves(self, loop):
        """Parte un contorno de labios en mitad superior e inferior, ordenadas por x."""
        P = self.face.px
        pts = P(loop)
        i0, i1 = int(pts[:, 0].argmin()), int(pts[:, 0].argmax())
        lo, hi = sorted((i0, i1))
        a = pts[lo:hi + 1]
        b = np.vstack([pts[hi:], pts[:lo + 1]])
        upper, lower = (a, b) if a[:, 1].mean() < b[:, 1].mean() else (b, a)
        return upper[np.argsort(upper[:, 0])], lower[np.argsort(lower[:, 0])]

    def teeth(self, svg):
        """Dos filas de dientes: los de arriba van del labio superior a la mordida y los de
        abajo de la mordida al labio inferior, así se separan al abrir la boca."""
        face, EW, T = self.face, self.EW, TEETH
        up_o, lo_o = self.lip_curves(face.lips_outer)
        up_i, lo_i = self.lip_curves(face.lips_inner)
        x0, x1 = up_o[0, 0], up_o[-1, 0]
        ext, gap = T["ext"] * EW, T["gap"] * EW

        def at(curve, x):
            return np.interp(x, curve[:, 0], curve[:, 1])

        def top(x):      # borde superior de los dientes de arriba (sobre el labio)
            return at(up_o, x) - ext * (1 - 0.5 * ((x - (x0 + x1) / 2) / ((x1 - x0) / 2)) ** 2)

        def bottom(x):   # borde inferior de los dientes de abajo
            return at(lo_o, x) + ext * (1 - 0.5 * ((x - (x0 + x1) / 2) / ((x1 - x0) / 2)) ** 2)

        xs = np.linspace(x0, x1, 40)
        back = np.vstack([np.stack([xs, top(xs) - gap], 1), np.stack([xs[::-1], bottom(xs[::-1]) + gap], 1)])
        svg.path("boca", bezier_d(resample(back, 48)), fill=INK, extra='id="encias"')

        # Anchos: más grandes al centro, más chicos hacia las comisuras.
        k = (np.arange(T["count"]) + 0.5) / T["count"]
        w = 1 - 0.45 * np.abs(2 * k - 1)
        edges = x0 + (x1 - x0) * np.concatenate([[0], np.cumsum(w) / w.sum()])
        def tooth(xa, xb, ya, yb, round_out):
            """Diente entre xa..xb; ya = borde hacia el labio, yb = borde de la mordida."""
            w, h = xb - xa, abs(yb - ya)
            r = min(0.35 * w, 0.4 * h)
            ro = r if round_out else r * 0.5      # el borde de la encía, menos redondeado
            sy = 1 if yb > ya else -1             # de arriba hacia abajo o al revés
            return (f"M{xa:.1f},{ya + sy * ro:.1f}Q{xa:.1f},{ya:.1f} {xa + ro:.1f},{ya:.1f}"
                    f"L{xb - ro:.1f},{ya:.1f}Q{xb:.1f},{ya:.1f} {xb:.1f},{ya + sy * ro:.1f}"
                    f"L{xb:.1f},{yb - sy * r:.1f}Q{xb:.1f},{yb:.1f} {xb - r:.1f},{yb:.1f}"
                    f"L{xa + r:.1f},{yb:.1f}Q{xa:.1f},{yb:.1f} {xa:.1f},{yb - sy * r:.1f}Z")

        teeth = []
        for xa, xb in zip(edges[:-1], edges[1:]):
            xa, xb = xa + gap / 2, xb - gap / 2
            xm = np.array([xa, (xa + xb) / 2, xb])
            # Arriba: del labio superior a la mordida; abajo: de la mordida al labio inferior.
            teeth.append(tooth(xa, xb, top(xm).max() + gap / 2, at(up_i, xm).min() - gap / 2, False))
            teeth.append(tooth(xa, xb, bottom(xm).min() - gap / 2, at(lo_i, xm).max() + gap / 2, False))
        svg.path("boca", "".join(teeth), fill=TOOTH, extra='id="dientes"')

    # frente: flor de cempasúchil al centro y papel picado arriba
    def forehead(self, svg, pal):
        face, EW = self.face, self.EW
        P = face.px
        brow_top = min(P(face.brow_upper["right"])[:, 1].min(), P(face.brow_upper["left"])[:, 1].min())
        oval_top = self.oval[:, 1].min()
        cx = P(face.nose_bridge)[:, 0].mean()
        cy = lerp(brow_top, oval_top, FLOWER["rise"])
        self.vines(svg, (cx, float(cy)), FLOWER["radius"] * EW)
        self.marigold(svg, "frente", pal, (cx, float(cy)), FLOWER["radius"] * EW, "flor-frente")
        self.papel_picado(svg, pal, oval_top, brow_top)

    def vines(self, svg, c, R):
        """Hojas detrás de la flor y una enredadera hacia cada sien, con hojas y un rizo."""
        EW, V = self.EW, VINES
        c = np.asarray(c, float)
        g = [f'<g id="hojas-frente" stroke="{INK}" stroke-width="{OUTLINE * EW:.1f}" stroke-linejoin="round">']
        for j, deg in enumerate((-150, -110, -70, -30, 30, 150)):
            a = math.radians(deg)
            base = c + 0.75 * R * np.array([math.cos(a), math.sin(a)])
            g.append(f'  <path d="{leaf_d(0.75 * R, 0.24 * R)}" fill="{LEAF[j % 2]}" transform="{place(*base, a)}"/>')
        for sx, n in ((-1, "right"), (1, "left")):
            ctrl = [c + R * np.array([sx * x, y]) for x, y in ((0.9, 0.25), (1.7, -0.15), (2.5, 0.05), (3.0, -0.35))]
            stem = resample(catmull(ctrl, False, 16), 40, closed=False)
            end = stem[-1]
            curl = spiral_pts(end + np.array([0, 0.28 * R]), 0.28 * R, 0.06 * R, -math.pi / 2, 0.9 * sx, 1, 30)
            svg.path("frente", bezier_d(resample(np.vstack([stem, curl[1:]]), 24, closed=False), closed=False),
                     stroke=VINE, width=V["stroke"] * EW, extra=f'id="enredadera-{n}"')
            tang = np.gradient(stem, axis=0)
            for k, t in enumerate((0.2, 0.42, 0.64, 0.84)):
                i = int(t * (len(stem) - 1))
                tx, ty = tang[i] / np.linalg.norm(tang[i])
                up = 1 if k % 2 else -1
                a = math.atan2(ty, tx) + up * math.radians(55) * sx
                L = V["leaves"] * R * (0.55 - 0.08 * k)
                g.append(f'  <path d="{leaf_d(L, L * V["leaf_w"])}" fill="{LEAF[(k + 1) % 2]}" '
                         f'transform="{place(*stem[i], a)}"/>')
        g.append("</g>")
        svg.add("frente", "\n    ".join(g))

    def marigold(self, svg, layer, pal, c, R, name):
        rings = [(1.00, 14, "petal_a"), (0.80, 12, "petal_b"), (0.60, 10, "petal_a"), (0.40, 8, "petal_b")]
        g = [f'<g id="{name}" stroke="{INK}" stroke-width="{OUTLINE * self.EW:.1f}" stroke-linejoin="round">']
        for k, (scale, count, color) in enumerate(rings):
            d = ruffled_ring_petal(R * 0.15, R * scale, math.pi / count * 1.25)
            for j in range(count):
                ang = 2 * math.pi * (j + 0.5 * k) / count - math.pi / 2
                g.append(f'  <path d="{d}" fill="{pal[color]}" transform="{place(*c, ang)}"/>')
        g.append(f'  <path d="{circle_d(c, R * 0.22)}" fill="{pal["flower_center"]}"/>')
        for j in range(5):
            a = 2 * math.pi * j / 5 - math.pi / 2
            g.append(f'  <path d="{circle_d((c[0] + R * 0.1 * math.cos(a), c[1] + R * 0.1 * math.sin(a)), R * 0.035)}" '
                     f'fill="{INK}" stroke="none"/>')
        g.append("</g>")
        svg.add(layer, "\n    ".join(g))

    def papel_picado(self, svg, pal, oval_top, brow_top):
        EW, cfg = self.EW, PICADO
        oval = resample(self.oval, 400)
        inner = oval - normals(oval) * cfg["inset"] * EW
        y_cut = lerp(oval_top, brow_top, cfg["cut"])
        keep = inner[:, 1] < y_cut
        # Tramo superior ordenado de izquierda a derecha (el óvalo es cerrado: rotar).
        start = int(np.argmax(~keep))
        idx = np.roll(np.arange(len(inner)), -start)
        arc = inner[idx][keep[idx]]
        arc = arc[np.argsort(arc[:, 0])]
        arc = catmull(resample(arc, 24, closed=False), closed=False, n=8)
        svg.path("frente", bezier_d(resample(arc, 16, closed=False), closed=False),
                 stroke=INK, width=cfg["string"] * EW, extra='id="cordel"')

        seg = np.linalg.norm(np.diff(arc, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        w, h, gap = cfg["width"] * EW, cfg["height"] * EW, cfg["gap"] * EW
        n = int((s[-1] + gap) // (w + gap))
        if n % 2 == 0:
            n -= 1  # número impar: una bandera queda al centro
        used = n * w + (n - 1) * gap
        flag = self.flag_d(w, h)
        g = ['<g id="papel-picado">']
        for k in range(n):
            sk = (s[-1] - used) / 2 + w / 2 + k * (w + gap)
            x, y = np.interp(sk, s, arc[:, 0]), np.interp(sk, s, arc[:, 1])
            i = min(int(np.searchsorted(s, sk)), len(arc) - 1)
            t = arc[min(i + 1, len(arc) - 1)] - arc[max(i - 1, 0)]
            color = pal["picado_a"] if k % 2 == 0 else pal["picado_b"]
            g.append(f'  <path d="{flag}" fill="{color}" fill-rule="evenodd" '
                     f'transform="{place(x, y, math.atan2(t[1], t[0]))}"/>')
        g.append("</g>")
        svg.add("frente", "\n    ".join(g))

    @staticmethod
    def flag_d(w, h):
        """Banderita de papel picado colgando del cordel (y local hacia abajo), con flecos
        en zigzag y figuras recortadas (regla evenodd)."""
        teeth = 4
        d = [f"M{-w / 2:.1f},0H{w / 2:.1f}V{h * 0.84:.1f}"]
        for k in range(teeth):
            xa = w / 2 - w * (k + 0.5) / teeth
            xb = w / 2 - w * (k + 1) / teeth
            d.append(f"L{xa:.1f},{h:.1f}L{xb:.1f},{h * 0.84:.1f}")
        d.append("Z")
        # Recortes: rombo central, dos puntos arriba y un triángulo abajo.
        cy, rx, ry = h * 0.44, w * 0.2, h * 0.17
        d.append(f"M0,{cy - ry:.1f}L{rx:.1f},{cy:.1f}L0,{cy + ry:.1f}L{-rx:.1f},{cy:.1f}Z")
        for sx in (-1, 1):
            d.append(circle_d((sx * w * 0.27, h * 0.17), w * 0.075))
        d.append(f"M{-w * 0.12:.1f},{h * 0.68:.1f}L{w * 0.12:.1f},{h * 0.68:.1f}L0,{h * 0.78:.1f}Z")
        return "".join(d)

    # mejillas: voluta en espiral con cola hacia la boca y puntos decorativos
    def cheek(self, svg, pal, side):
        face, EW = self.face, self.EW
        S = self.skull_points(side)
        sock = self.socket(side)
        sock_out = sock[np.argmax(side.sx * sock[:, 0] + sock[:, 1])]   # abajo y afuera de la cuenca
        c = lerp(S["cheek"], sock_out, CHEEK["out"]) + np.array([0.0, 0.15 * EW])

        r1 = CHEEK["spiral"] * EW
        turns = CHEEK["turns"]
        a_end = math.pi / 2                                   # termina abajo...
        spiral = spiral_pts(c, 0.12 * r1, r1, a_end - 2 * math.pi * turns, turns, side.sx)
        end = spiral[-1]
        tail_end = lerp(c, S["notch"], 0.62)                          # ...y la cola baja hacia la muesca
        tail = catmull([end, lerp(end, tail_end, 0.5) + np.array([0, 0.45 * r1]), tail_end],
                       closed=False, n=16)
        curve = np.vstack([spiral, tail[1:]])
        svg.path("mejillas", bezier_d(resample(curve, 40, closed=False), closed=False),
                 stroke=pal["scroll"], width=CHEEK["stroke"] * EW, extra=f'id="voluta-{side.name}"')
        # Rizo pequeño al final de la cola, girando al revés.
        r2 = 0.45 * r1
        t = tail[-1] - tail[-3]
        t /= np.linalg.norm(t)
        c2 = tail_end + np.array([-t[1], t[0]]) * r2 * (1 if side.sx > 0 else -1) * -1
        a0 = math.atan2((tail_end - c2)[1], side.sx * (tail_end - c2)[0])
        curl = spiral_pts(c2, r2, 0.25 * r2, a0, -0.85, side.sx, 40)
        svg.path("mejillas", bezier_d(resample(curl, 14, closed=False), closed=False),
                 stroke=pal["scroll"], width=CHEEK["stroke"] * EW * 0.8, extra=f'id="rizo-{side.name}"')

        dots = []
        for k, size in enumerate((1.0, 0.8, 0.62, 0.48)):
            a = -math.pi / 2 - (0.35 + 0.42 * k)               # arco arriba y hacia afuera
            rr = r1 * 1.55
            p = (c[0] + side.sx * rr * math.cos(a) * -1, c[1] + rr * math.sin(a))
            dots.append(circle_d(p, CHEEK["dot"] * EW * size))
        svg.path("mejillas", "".join(dots), fill=pal["dots"], extra=f'id="puntos-{side.name}"')

    # mentón: florecita de cinco pétalos con dos rizos
    def chin(self, svg, pal):
        face, EW = self.face, self.EW
        lips = face.px(face.lips_outer)
        c = np.array([face.px(face.nose_bridge)[:, 0].mean(),
                      lerp(lips[:, 1].max(), self.oval[:, 1].max(), CHIN["at"])])
        g = [f'<g id="ornamento-menton" stroke="{INK}" stroke-width="{OUTLINE * EW:.1f}" stroke-linejoin="round">']
        d = petal_d(CHIN["petal"] * EW, CHIN["petal"] * 0.42 * EW)
        for j in range(5):
            ang = math.pi / 2 + 2 * math.pi * j / 5
            g.append(f'  <path d="{d}" fill="{pal["chin"]}" transform="{place(*c, ang)}"/>')
        g.append(f'  <path d="{circle_d(c, CHIN["petal"] * 0.28 * EW)}" fill="{BONE}"/>')
        g.append("</g>")
        svg.add("menton", "\n    ".join(g))
        for sx, name in ((-1, "right"), (1, "left")):
            r = CHIN["curl"] * EW
            cc = c + np.array([sx * CHIN["petal"] * EW * 1.55, -0.2 * r])
            curl = spiral_pts(cc, 0.2 * r, r, -math.pi * 0.5 - 2 * math.pi * 1.1, 1.1, sx, 50)
            svg.path("menton", bezier_d(resample(curl, 16, closed=False), closed=False),
                     stroke=pal["chin"], width=CHIN["stroke"] * EW, extra=f'id="rizo-menton-{name}"')

    # transparencias: huecos exactos con los contornos de ojos e interior de los labios
    def holes(self, svg):
        P = self.face.px
        for side in ("right", "left"):
            svg.path("transparencias", poly_d(P(self.face.eye[side])), fill=HOLE, extra=f'id="hueco-ojo-{side}"')
        svg.path("transparencias", poly_d(P(self.face.lips_inner)), fill=HOLE, extra='id="hueco-boca"')


LAYERS = ["base", "huesos", "craneo", "frente", "mejillas", "menton", "nariz", "boca", "ojos", "transparencias", "referencia"]


def preview(paths, out, size=1024, bg=(92, 78, 70)):
    tiles = []
    for p in paths:
        rgba, _ = svglib.render_with_holes(open(p, encoding="utf-8").read(), size)
        tile = Image.new("RGBA", (size, size), bg + (255,))
        tile.alpha_composite(svglib.to_image(rgba))
        tiles.append(tile)
    sheet = Image.new("RGB", (size * len(tiles), size))
    for i, t in enumerate(tiles):
        sheet.paste(t.convert("RGB"), (i * size, 0))
    sheet.save(out, optimize=True)


def main():
    face = Face(SIZE)
    design = Design(face)
    print(f"[03] ancho de ojo: {design.EW:.0f} px; error de simetría UV: {face.mirror_error_px():.1f} px")
    os.makedirs(DESIGN_DIR, exist_ok=True)
    paths = []
    for name, pal in PALETTES.items():
        path = os.path.join(DESIGN_DIR, f"{name}.svg")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(design.build(pal).text(LAYERS, f"Calavera de Día de Muertos ({name})"))
        paths.append(path)
        print(f"[03] {path}")
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    preview(paths, PREVIEW)
    print(f"[03] vista previa: {PREVIEW}")


if __name__ == "__main__":
    main()
