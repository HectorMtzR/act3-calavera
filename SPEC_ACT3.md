# Calavera AR — Especificación del proyecto

> Documento para desarrollar con Claude Code. Actividad 3 del curso de Realidad Virtual y Aumentada:
> "Máscara de Día de Muertos con mapeo facial de precisión".
> **Fecha de entrega: 26 de octubre de 2026.**
>
> **Punto de partida:** el proyecto de la Actividad 2 (Máscara de Lava AR). Se copia a un **repositorio nuevo**,
> porque esta actividad se califica de forma independiente.

---

## 1. Resumen

Filtro facial web para celular. Al abrir la página se activa la cámara frontal y el rostro se cubre con una **calavera de Día de Muertos** pintada sobre la malla facial, como si fuera **maquillaje**: los elementos del diseño quedan alineados con **ojos, nariz, boca y contorno**, y la máscara se estira con los gestos sin desprenderse.

- **Gesto principal:** al **abrir la boca**, cae una **lluvia de pétalos de cempasúchil**.
- **Gesto secundario:** al **levantar las cejas**, la máscara **cambia de paleta de colores** (variante de flores y papel picado).

### Qué cambia respecto a la Actividad 2
| | Actividad 2 (lava) | Actividad 3 (calavera) |
|---|---|---|
| Textura | Procedural (ruido), no depende de los rasgos | **Dibujada a partir de los puntos de los rasgos** (ojos, labios, nariz, contorno) |
| Resolución | Sprite sheet de 16 cuadros de 512 px | **Textura fija de 2048 px**, más nítida |
| Ojos y boca | Transparencia aproximada | **Transparencia exacta** con el contorno de ojos y labios |
| Bordes | Corte duro en el contorno | **Borde suave** en el contorno de la cara |
| Costuras | Sin tratamiento | **Relleno de bordes (padding)** para evitar costuras |
| Seguimiento | Landmarks directos | **Landmarks suavizados** (menos temblor) |
| Efecto | Erupción de lava | Pétalos de cempasúchil y cambio de paleta |

Esta tabla también es la base del artículo de LinkedIn, que debe explicar la mejora frente a la Act. 2.

---

## 2. Stack técnico

Igual que la Actividad 2:
- **HTML + CSS + JavaScript (ES modules)**, sin build. GitHub Pages.
- **MediaPipe Face Landmarker** (`@mediapipe/tasks-vision`) con blendshapes.
- **three.js** para la malla y el shader.
- **Blender 4.x en modo terminal** para la plantilla UV y la vista previa 3D.
- **Python** para generar el diseño como **SVG anclado a los landmarks** y rasterizarlo (cairosvg, resvg o similar; elegir el que funcione en el equipo).

---

## 3. Estructura del repositorio

Copiar el repo de la Act. 2 y ajustar:

```
/
├── index.html
├── css/style.css
├── js/
│   ├── main.js
│   ├── config.js      # ruta de texturas, paletas, gestos, efectos
│   ├── face.js        # + suavizado de landmarks (nuevo)
│   ├── mask.js        # + mezcla entre dos texturas y filtros de calidad (nuevo)
│   ├── gestures.js
│   ├── effects.js     # pétalos y cambio de paleta (reemplaza la erupción)
│   └── audio.js
├── assets/
│   ├── face/
│   │   ├── canonical_face_model.obj
│   │   ├── uv_template.png
│   │   └── uv_guide.png          # guía con los contornos de los rasgos (nuevo)
│   ├── mask/
│   │   ├── calavera.png          # textura principal 2048×2048 con alfa
│   │   └── calavera_alt.png      # misma calavera con la paleta alternativa
│   ├── particles/
│   │   └── petal.png             # pétalo de cempasúchil
│   └── sounds/
├── design/
│   ├── calavera.svg              # diseño fuente (editable a mano)
│   └── calavera_alt.svg
├── tools/
│   ├── 01_uv_template.py         # (reutilizado de la Act. 2)
│   ├── 02_uv_guide.py            # dibuja contornos de rasgos en espacio UV
│   ├── 03_generate_svg.py        # genera el diseño anclado a landmarks
│   ├── 04_rasterize.py           # SVG → PNG 2048 con alfa, borde suave y padding
│   └── 05_preview_blender.py     # render 3D de la máscara sobre la malla canónica
├── docs/screenshots/
├── README.md
└── SPEC_ACT3.md
```

Quitar del repo todo lo que sea exclusivo de la lava (sprite sheet, scripts de lava, sonidos de fuego).

---

## 4. Diseño de la calavera

### Concepto
Calavera de azúcar / catrina, **festiva y respetuosa**: celebra la memoria de quienes ya no están. Nada de estilo zombie, sangre o terror.

### Elementos y ubicación
| Zona | Elemento | Color |
|---|---|---|
| Base (toda la cara) | Blanco hueso | `#f4efe6` |
| Alrededor de los ojos | Cuenca oscura que sigue el contorno del ojo, con un **anillo de pétalos de cempasúchil** | Cuenca `#1b1b1b`; pétalos `#ff8c00` / `#ffb703` |
| Punta de la nariz | **Corazón invertido** negro sobre la nariz | `#1b1b1b` |
| Boca | Labios oscuros y **líneas verticales** que cruzan los labios y se extienden un poco hacia las mejillas (dientes) | `#1b1b1b` |
| Frente | **Flor de cempasúchil** al centro y una banda de **papel picado** en la parte alta | Flor naranja/amarillo; papel picado `#e4007c` / `#7b2cbf` |
| Mejillas | Volutas y puntos decorativos | Rosa mexicano / turquesa `#00a6a6` |
| Mentón | Ornamento pequeño (espiral o flor) | `#7b2cbf` |

### Paleta alternativa (gesto de cejas)
Mismo diseño; cambian los acentos: flores en **morado y rosa**, papel picado en **naranja y amarillo**, volutas en **dorado** `#d4a017`. La base y las zonas negras no cambian.

### Reglas de diseño
- **Simetría:** diseñar media cara y reflejar usando los pares de landmarks izquierdo/derecho.
- **Colores saturados y contornos definidos** (grosor de línea suficiente): el detalle fino se pierde en cámara.
- **Ojos y boca interior transparentes.**
- **Borde suave** en el contorno de la cara (desvanecido de unos pocos píxeles) para que no se vea un corte.

---

## 5. Herramientas de la textura

### 01 — Plantilla UV
Reutilizar el script de la Act. 2. Exportar a 2048×2048.

### 02 — Guía UV (`02_uv_guide.py`)
- Leer las UVs del `canonical_face_model.obj`.
- Usar los **conjuntos oficiales de conexiones de MediaPipe** para ubicar los rasgos (no escribir índices a mano):
  `FACE_LANDMARKS_LEFT_EYE`, `FACE_LANDMARKS_RIGHT_EYE`, `FACE_LANDMARKS_LIPS`, `FACE_LANDMARKS_FACE_OVAL`, `FACE_LANDMARKS_LEFT_EYEBROW`, `FACE_LANDMARKS_RIGHT_EYEBROW` (y la punta de la nariz).
- Dibujar esos contornos sobre la plantilla y guardarlos en `assets/face/uv_guide.png`.
- **Verificar** que "izquierdo/derecho" corresponden a lo esperado (en MediaPipe son desde la perspectiva de la persona).

### 03 — Diseño SVG (`03_generate_svg.py`)
- Generar `design/calavera.svg` y `design/calavera_alt.svg` en espacio UV (2048×2048).
- Cada elemento se **posiciona y escala a partir de los landmarks** de su zona (por ejemplo, la cuenca de los ojos se construye con el contorno del ojo agrandado; las líneas de los dientes se reparten sobre el contorno de los labios).
- Organizar el SVG en **capas con nombre** (`base`, `ojos`, `nariz`, `boca`, `frente`, `mejillas`, `menton`, `transparencias`) para que se pueda **retocar a mano** en Figma, Inkscape o Illustrator.
- La capa `transparencias` define los huecos exactos de ojos y boca a partir de sus contornos.

### 04 — Rasterizado (`04_rasterize.py`)
- SVG → PNG **2048×2048 con canal alfa**.
- **Padding:** extender los colores unos píxeles más allá de las islas UV para evitar costuras con el filtrado de texturas.
- Borde suave en el contorno facial.
- Salida: `assets/mask/calavera.png` y `assets/mask/calavera_alt.png`. Optimizar peso (idealmente < 3 MB cada una).

### 05 — Vista previa en Blender (`05_preview_blender.py`)
- Aplicar la textura a la malla canónica y renderizar 3 vistas (frente, ¾ izquierdo, ¾ derecho) en `docs/screenshots/`.
- Sirve para revisar antes de probar en el celular y para el README y el artículo.

### Revisión visual
Después de cada paso, **abrir y revisar las imágenes** generadas (guía, SVG rasterizado, vista previa). Corregir alineación, grosor de líneas y transparencias antes de pasar al celular.

---

## 6. Mejoras de precisión en el filtro

### Suavizado de landmarks (`face.js`)
- Aplicar un filtro **One Euro** (o similar) por landmark para reducir el temblor sin generar retraso visible.
- Parámetros en `config.js` para ajustarlos.

### Calidad de textura (`mask.js`)
- `generateMipmaps` activado, `anisotropy` al máximo que permita el dispositivo, `colorSpace` sRGB.
- Shader con dos texturas (`uMaskA`, `uMaskB`) y un `uniform float uMix` para mezclar la paleta principal con la alternativa.

### Modo depuración
Con `?debug=1`: mostrar encima los **contornos de ojos, labios y cara en tiempo real** (puntos o líneas) y los valores de los blendshapes. Sirve para comprobar que la máscara queda alineada con los rasgos reales.

---

## 7. Gestos y efectos

| Gesto | Blendshape | Umbral | Pausa | Efecto |
|---|---|---|---|---|
| Abrir la boca | `jawOpen` | > 0.5 | 1.0 s | **Lluvia de pétalos de cempasúchil** |
| Levantar las cejas | `browInnerUp` | > 0.5 | 1.5 s | **Cambio de paleta** (alterna entre principal y alternativa) |

### Pétalos (`effects.js`)
- Partículas con `petal.png` (pétalo naranja/amarillo, 64–128 px, con transparencia).
- Caen desde arriba de la cabeza, con **rotación**, **balanceo lateral** y gravedad suave, durante ~2 s.
- Unos pocos pétalos también salen desde la boca.
- Sonido suave (por ejemplo, campanitas o viento ligero) con licencia libre.

### Cambio de paleta
- `uMix` transiciona de 0 a 1 (o de 1 a 0) en ~0.6 s con curva suave.
- Sonido corto opcional.

---

## 8. Inicio y UI

Igual que la Act. 2:
- **Abre directo al filtro**, sin menús.
- "Cargando…" mientras carga el modelo; "Muestra tu cara a la cámara" si no hay rostro.
- Botón 🔇/🔊 para desbloquear el audio.
- Instrucción breve: "Abre la boca 🌼 · Levanta las cejas 🎨".

---

## 9. Constantes (`config.js`)

```js
export const CONFIG = {
  MASK_A: "assets/mask/calavera.png",
  MASK_B: "assets/mask/calavera_alt.png",
  SMOOTHING: { minCutoff: 1.0, beta: 0.01 },   // filtro One Euro
  GESTURES: {
    jawOpen:     { threshold: 0.5, cooldown: 1.0 },
    browInnerUp: { threshold: 0.5, cooldown: 1.5 },
  },
  PETALS: { count: 80, duration: 2.0 },
  PALETTE_TRANSITION: 0.6,
};
```

---

## 10. Recursos externos y créditos

| Recurso | Fuente | Licencia |
|---|---|---|
| Malla canónica y Face Landmarker | MediaPipe (Google) | Apache 2.0 |
| three.js | threejs.org | MIT |
| Sonidos | Pixabay, Freesound o Kenney | Registrar la de cada archivo |
| Diseño de la calavera y pétalo | Propio | Propio |

---

## 11. README.md

1. Nombre y descripción.
2. Cómo se usa (gestos).
3. **Significado de los elementos** (sección breve): calavera, cempasúchil y papel picado en el Día de Muertos, con 2–3 referencias en **formato APA**.
4. Herramientas: MediaPipe, three.js, Blender, Python, Claude Code.
5. **Proceso de la textura:** plantilla UV → guía de rasgos → SVG anclado a landmarks → rasterizado → vista previa 3D. Con imágenes de cada paso.
6. **Mejoras frente a la Actividad 2** (la tabla de la sección 1) y capturas lado a lado.
7. Enlace para probarlo (GitHub Pages).
8. Instalación y ejecución local, incluyendo cómo regenerar la textura.
9. Capturas.
10. Créditos con licencia.
11. Autor.

---

## 12. Fases de desarrollo

Commit con mensaje claro al cerrar cada fase.

| Fase | Objetivo | Listo cuando… |
|---|---|---|
| 0. Base | Repo nuevo a partir de la Act. 2, sin lo exclusivo de la lava, publicado en GitHub Pages con la plantilla UV como textura | Se ve la plantilla bien alineada en el celular |
| 1. Guía | `uv_guide.png` con los contornos de los rasgos | Ojos, labios, nariz y contorno se ubican correctamente en la plantilla |
| 2. Diseño | SVG de la calavera anclado a landmarks, simétrico y con capas | El diseño revisado y aprobado por Héctor |
| 3. Textura | PNG 2048 con alfa, padding y borde suave; vista previa en Blender | Las 3 vistas previas se ven sin costuras y bien alineadas |
| 4. Precisión | Suavizado de landmarks, filtros de textura, modo debug con contornos | La máscara no tiembla y coincide con los rasgos al gesticular |
| 5. Efectos | Pétalos, cambio de paleta y sonidos | Ambos gestos responden de forma confiable |
| 6. Pulido | Pruebas, README con sección cultural y comparación, capturas | Lista la entrega |

---

## 13. Pruebas

- [ ] Probar en **al menos 2 teléfonos**.
- [ ] Probar en **varios rostros** (distintas formas de cara), con **lentes** y con distinta luz.
- [ ] Ojos, nariz, boca y contorno alineados al frente, de perfil (¾), mirando arriba y abajo.
- [ ] Al abrir la boca y sonreír, la máscara se estira sin desprenderse; los dientes pintados siguen los labios.
- [ ] Ojos y boca reales visibles; sin costuras ni pixelado visibles.
- [ ] Los gestos no se disparan al hablar normal.
- [ ] Abre directo al filtro desde el enlace, en ventana de incógnito.

---

## 14. Rúbrica y cómo se cubre

| Criterio | Pts | Cómo se cubre |
|---|---|---|
| Precisión del mapeo facial | 2.5 | Diseño anclado a los landmarks de cada rasgo + suavizado; se deforma con la malla sin desprenderse |
| Diseño temático original | 2 | Calavera propia con cempasúchil y papel picado, festiva y respetuosa, con sección de significado en el README |
| Calidad de la textura | 1.5 | 2048 px, padding contra costuras, ojos y boca transparentes, borde suave |
| Interactividad y efectos | 1.5 | Boca → pétalos de cempasúchil; cejas → cambio de paleta |
| Funcionamiento | 0.5 | Estable en el teléfono, abre directo |
| Repositorio GitHub | 1 | Código modular, herramientas de textura incluidas, README completo |
| Artículo LinkedIn | 1 | Proceso, retos y **mejora frente a la Act. 2**, con video y enlace |

---

## 15. Tareas manuales (las hace el equipo, no Claude Code)

- [ ] Revisar el diseño en la fase 2 y pedir ajustes (flores, grosor de líneas, colores).
- [ ] **Opcional, recomendado:** retocar a mano el SVG en Figma, Inkscape o Illustrator (agregar o mover flores, detalles propios). Refuerza el criterio de diseño original.
- [ ] Buscar 2–3 fuentes sobre el significado de los elementos para la sección cultural (APA).
- [ ] Descargar sonidos y anotar créditos.
- [ ] Probar con varias personas, con lentes y con distinta luz.
- [ ] Grabar el video demo (30–60 s) con buena luz; idealmente incluir un clip corto de la Act. 2 para mostrar la mejora.
- [ ] Escribir el artículo de LinkedIn explicando la mejora frente a la Act. 2, y mencionando con honestidad el uso de Claude Code en el proceso.
- [ ] Subir los 3 enlaces al formulario.
