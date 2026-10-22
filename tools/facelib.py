"""
Rasgos de la cara en espacio UV, a partir de los conjuntos oficiales de conexiones de
MediaPipe (`FaceLandmarksConnections`). Ningún índice de landmark se escribe a mano:
los contornos se arman encadenando las aristas de cada conjunto.

Lo usan 02_uv_guide.py y 03_generate_svg.py (Python normal, no dentro de Blender).
Requiere: pip install -r tools/requirements.txt

Convenciones:
- "izquierdo/derecho" son desde la perspectiva de la PERSONA, igual que en MediaPipe.
  En la textura (vista de frente) el lado izquierdo de la persona queda a la DERECHA.
- Coordenadas de imagen en píxeles: x hacia la derecha, y hacia ABAJO (como SVG y PNG).
"""
from collections import defaultdict

import numpy as np
from mediapipe.tasks.python.vision import FaceLandmarksConnections as MP

from uvlib import load_canonical_obj

SIZE = 2048


def _edges(name):
    return [(c.start, c.end) for c in getattr(MP, f"FACE_LANDMARKS_{name}")]


def _chains(edges):
    """Encadena aristas en recorridos. Devuelve [(índices, cerrado)], abiertos primero
    desde un extremo; los cerrados no repiten el primer punto al final."""
    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    seen, out = set(), []
    starts = [v for v in adj if len(adj[v]) == 1] + list(adj)
    for s in starts:
        if s in seen:
            continue
        path, prev, cur = [s], None, s
        seen.add(s)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            path.append(cur)
        closed = len(path) > 2 and s in adj[path[-1]]
        out.append((path, closed))
    return out


def _loop(name):
    chains = _chains(_edges(name))
    assert len(chains) == 1 and chains[0][1], f"{name}: se esperaba un solo contorno cerrado"
    return chains[0][0]


def polygon_area(pts):
    x, y = np.asarray(pts, dtype=float).T
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


class Face:
    """Malla canónica + contornos de los rasgos.

    Atributos (listas de índices de landmark, en orden):
      oval, eye[side], lips_outer, lips_inner, brow_upper[side], brow_lower[side],
      nose_bridge (de la raíz a la base), nostrils (contorno de las aletas), nose_tip.
    `side` es "left" o "right" (de la persona).
    """

    def __init__(self, size=SIZE):
        self.size = size
        self.verts, self.uvs, self.tris = load_canonical_obj()
        self.oval = _loop("FACE_OVAL")
        self.eye = {"left": _loop("LEFT_EYE"), "right": _loop("RIGHT_EYE")}

        # Labios: dos contornos cerrados; el exterior es el de mayor área.
        lips = _chains(_edges("LIPS"))
        assert len(lips) == 2 and all(c for _, c in lips)
        lips = sorted((p for p, _ in lips), key=lambda p: abs(polygon_area(self.uv(p))))
        self.lips_inner, self.lips_outer = lips

        # Cejas: dos líneas abiertas; la superior es la de mayor v promedio.
        self.brow_upper, self.brow_lower = {}, {}
        for side in ("left", "right"):
            lines = [p for p, _ in _chains(_edges(f"{side.upper()}_EYEBROW"))]
            lines.sort(key=lambda p: self.uvs[p, 1].mean())
            self.brow_lower[side], self.brow_upper[side] = lines
            for line in lines:  # de adentro (cerca de la nariz) hacia afuera
                if abs(self.verts[line[0], 0]) > abs(self.verts[line[-1], 0]):
                    line.reverse()

        self._split_nose()

        self.mirror = self._mirror_map()
        self._check_sides()

    # ---------- coordenadas ----------
    def uv(self, idx):
        return self.uvs[np.asarray(idx)]

    def px(self, idx):
        """Landmark(s) → píxeles de imagen (y hacia abajo)."""
        uv = self.uv(idx)
        return np.stack([uv[..., 0] * self.size, (1 - uv[..., 1]) * self.size], axis=-1)

    # ---------- simetría ----------
    def _mirror_map(self):
        """Par izquierdo/derecho de cada landmark: el vértice más cercano a (-x, y, z)."""
        flipped = self.verts * [-1, 1, 1]
        d = np.linalg.norm(flipped[:, None, :] - self.verts[None, :, :], axis=2)
        m = d.argmin(1)
        assert (m[m] == np.arange(len(m))).all(), "el mapa de simetría no es una involución"
        return m

    def mirror_error_px(self):
        """Máxima diferencia (px) entre la UV de un punto y la de su par reflejado."""
        a = self.px(np.arange(len(self.uvs)))
        b = self.px(self.mirror)
        b[:, 0] = self.size - b[:, 0]
        return float(np.abs(a - b).max())

    # ---------- verificación ----------
    def _check_sides(self):
        """En MediaPipe "izquierdo" es el de la persona: x > 0 en la malla canónica y
        a la derecha de la imagen de la textura (vista de frente)."""
        for side, sign in (("left", 1), ("right", -1)):
            for ids in (self.eye[side], self.brow_upper[side]):
                assert np.sign(self.verts[ids, 0].mean()) == sign, f"{side}: x canónico inesperado"
                assert np.sign(self.uvs[ids, 0].mean() - 0.5) == sign, f"{side}: u inesperada"
        mid = self.nose_bridge + [self.nose_tip]
        assert np.allclose(self.verts[mid, 0], 0, atol=1e-3), "la nariz no está en el eje"

    def _split_nose(self):
        """El conjunto NOSE es un puente (raíz → base) que cruza el contorno de las aletas.
        Puente = camino más corto entre la raíz (único extremo libre) y la base (el vértice
        de grado 3); aletas = las aristas restantes, que forman un contorno cerrado."""
        edges = _edges("NOSE")
        adj = defaultdict(list)
        for a, b in edges:
            adj[a].append(b)
            adj[b].append(a)
        root = next(v for v in adj if len(adj[v]) == 1)
        base = next(v for v in adj if len(adj[v]) == 3)
        prev, queue = {root: None}, [root]
        for cur in queue:
            for n in adj[cur]:
                if n not in prev:
                    prev[n] = cur
                    queue.append(n)
        path, cur = [], base
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        self.nose_bridge = path[::-1]

        used = set(zip(path, path[1:])) | set(zip(path[1:], path))
        loops = [p for p, closed in _chains([e for e in edges if e not in used]) if closed]
        assert len(loops) == 1, "no se encontró el contorno de las aletas de la nariz"
        self.nostrils = loops[0]
        # Punta: el punto más adelantado (mayor z) de la nariz en la malla canónica.
        self.nose_tip = max(adj, key=lambda i: self.verts[i, 2])

    def summary(self):
        return {
            "óvalo": len(self.oval),
            "ojo izq.": len(self.eye["left"]),
            "ojo der.": len(self.eye["right"]),
            "labios ext./int.": (len(self.lips_outer), len(self.lips_inner)),
            "punta de nariz": self.nose_tip,
            "error de simetría UV (px)": round(self.mirror_error_px(), 1),
        }
