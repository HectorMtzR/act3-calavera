// Todas las constantes ajustables del filtro.

const MEDIAPIPE_VERSION = "0.10.14";

export const CONFIG = {
  // --- Malla facial ---
  FACE_MODEL: "assets/face/canonical_face_model.obj",
  UV_TEMPLATE: "assets/face/uv_template.png",
  UV_GUIDE: "assets/face/uv_guide.png",        // contornos de ojos, labios, nariz y cara

  // --- Máscara (2048×2048 con alfa; se generan con tools/04_rasterize.py) ---
  // Mientras no existan, se usa la plantilla UV en su lugar.
  MASK_A: "assets/mask/calavera.png",          // paleta principal
  MASK_B: "assets/mask/calavera_alt.png",      // paleta alternativa (gesto de cejas)

  // Quitar de la malla los triángulos que tapan ojos y boca (transparencia exacta, sin
  // depender del alfa de la textura).
  MASK_CUT_HOLES: true,

  // --- Suavizado de landmarks (filtro One Euro, en píxeles del video) ---
  // minCutoff (Hz): menos = menos temblor en reposo, más retraso.
  // beta: cuánto sube el corte con la velocidad; más = menos retraso al moverse rápido.
  // Con ?smooth=0 empieza desactivado; en ?debug=1 la tecla S lo alterna.
  SMOOTHING: { enabled: true, minCutoff: 1.0, beta: 0.01, dCutoff: 1.0 },

  // --- Gestos (blendshapes de MediaPipe) ---
  GESTURES: {
    jawOpen:     { threshold: 0.5, cooldown: 1.0 },   // lluvia de pétalos
    browInnerUp: { threshold: 0.5, cooldown: 1.5 },   // cambio de paleta
  },
  // Histéresis: tras disparar, el gesto se rearma cuando baja de threshold * GESTURE_RELEASE.
  GESTURE_RELEASE: 0.8,

  // --- Efectos ---
  // Lluvia de pétalos (boca abierta). Distancias en "anchos de cara" (entre las comisuras
  // externas de los ojos), así el efecto escala con lo cerca que esté la persona.
  PETALS: {
    count: 80,               // pétalos que caen desde arriba de la cabeza
    mouth: 12,               // pétalos extra que salen de la boca
    duration: 2.0,           // s, duración de la lluvia
    sprite: "assets/particles/petal.png",
    size: [0.22, 0.38],      // tamaño de cada pétalo
    spread: 1.8,             // ancho de la zona de donde caen (a cada lado del centro)
    height: [0.6, 1.6],      // altura sobre la frente donde aparecen
    gravity: 1.4,
    terminal: 1.5,           // velocidad máxima de caída
    sway: 0.45,              // balanceo lateral
    mouthSpeed: [1.6, 2.6],
  },
  PALETTE_TRANSITION: 0.6,   // s, cambio de paleta (uMix 0 <-> 1)

  // --- Audio ---
  EFFECT_VOLUME: 0.9,
  // Archivos de sonido opcionales por efecto (p. ej. "assets/sounds/petals.mp3"). Con null
  // se usa el sonido sintetizado con Web Audio (campanitas y viento / brillo).
  SOUNDS: {
    petals: null,
    palette: null,
  },

  // --- MediaPipe Face Landmarker ---
  MEDIAPIPE: {
    WASM_URL: `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`,
    MODEL_URL:
      "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    NUM_FACES: 1,
    MIN_DETECTION_CONFIDENCE: 0.5,
    MIN_TRACKING_CONFIDENCE: 0.5,
  },

  // --- Cámara ---
  CAMERA: {
    FACING_MODE: "user",
    IDEAL_WIDTH: 1280,
    IDEAL_HEIGHT: 720,
    MIRROR: true,            // vista tipo selfie
  },

  // --- Depuración (?debug=1) ---
  DEBUG_POINT_SIZE: 2,       // px, puntos de landmarks SIN suavizar
  DEBUG_POINT_COLOR: 0xffffff,
  // Contornos (suavizados) en tiempo real, mismos colores que la guía UV.
  DEBUG_CONTOURS: {
    FACE_OVAL: 0xffd600,
    LEFT_EYE: 0x00dcff,
    RIGHT_EYE: 0x00ff8c,
    LEFT_EYEBROW: 0xaaff3c,
    RIGHT_EYEBROW: 0xaaff3c,
    LIPS: 0xff2878,
  },
};
