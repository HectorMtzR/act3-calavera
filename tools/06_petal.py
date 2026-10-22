"""
06 — Pétalo de cempasúchil para la lluvia de pétalos (sprite de partículas).

Uso (desde la raíz del repo):
    python tools/06_petal.py

Salida: assets/particles/petal.png (128x128 con alfa). El pétalo apunta hacia arriba y
cabe dentro del círculo inscrito, así se puede girar en el shader sin recortarse.
El shader lo tiñe un poco por partícula (de amarillo a naranja).
"""
import os

import svglib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "particles", "petal.png")
SIZE = 128

# Coordenadas en una caja de 100x100 con el centro en (50, 50); se escala a SIZE.
SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="g" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" stop-color="#e85d04"/>
      <stop offset="0.55" stop-color="#ff8c00"/>
      <stop offset="1" stop-color="#ffb703"/>
    </linearGradient>
  </defs>
  <!-- Base angosta abajo, punta ancha con tres ondas arriba (como en el diseño). -->
  <path d="M50,90 C38,84 26,62 26,40 C26,26 30,16 36,13 Q40,8 44,12 Q50,5 56,12 Q60,8 64,13
           C70,16 74,26 74,40 C74,62 62,84 50,90 Z"
        fill="url(#g)" stroke="#b34700" stroke-width="2.2" stroke-linejoin="round"/>
  <!-- Venas -->
  <g fill="none" stroke="#c2410c" stroke-width="1.6" stroke-linecap="round" opacity="0.7">
    <path d="M50,86 C50,62 50,38 50,18"/>
    <path d="M50,80 C44,62 39,44 38,26"/>
    <path d="M50,80 C56,62 61,44 62,26"/>
  </g>
</svg>
"""


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    svglib.to_image(svglib.render(SVG, SIZE)).save(OUT, optimize=True)
    print(f"[06] listo: {OUT}")


if __name__ == "__main__":
    main()
