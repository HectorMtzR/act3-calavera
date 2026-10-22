// Arranque: cámara frontal, MediaPipe y render loop.
import * as THREE from "three";
import { FaceLandmarker } from "@mediapipe/tasks-vision";
import { CONFIG } from "./config.js";
import { createFaceTracker } from "./face.js";
import { createScene } from "./scene.js";
import { createMask } from "./mask.js";
import { createGestureDetector } from "./gestures.js";
import { createEffects } from "./effects.js";
import { unlockAudio, isUnlocked, setMuted, isMuted } from "./audio.js";

const params = new URLSearchParams(location.search);
const DEBUG = params.get("debug") === "1";
// ?template=1 muestra la plantilla UV y ?guide=1 la guía con los contornos de los rasgos
// en lugar de la máscara (para revisar la alineación).
const STATIC_TEXTURE = params.get("guide") === "1" ? CONFIG.UV_GUIDE
  : params.get("template") === "1" ? CONFIG.UV_TEMPLATE : null;
const MASK_TEXTURES = STATIC_TEXTURE
  ? { a: STATIC_TEXTURE, b: STATIC_TEXTURE }
  : { a: CONFIG.MASK_A, b: CONFIG.MASK_B };
const SMOOTH = params.get("smooth") !== "0";
const NUM_MESH_POINTS = 478; // 468 de la cara + 10 del iris

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const ui = {
  loading: document.getElementById("loading"),
  noFace: document.getElementById("no-face"),
  error: document.getElementById("error"),
  hint: document.getElementById("hint"),
  sound: document.getElementById("sound"),
  debug: document.getElementById("debug"),
};

function show(el, visible) {
  el.hidden = !visible;
}

function showError(title, detail) {
  show(ui.loading, false);
  show(ui.noFace, false);
  show(ui.hint, false);
  ui.error.innerHTML = `<strong>${title}</strong><p>${detail}</p>`;
  show(ui.error, true);
}

// ---------- Cámara ----------
async function startCamera() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    throw Object.assign(new Error("insecure"), { name: "InsecureContext" });
  }
  const cam = CONFIG.CAMERA;
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: {
      facingMode: cam.FACING_MODE,
      width: { ideal: cam.IDEAL_WIDTH },
      height: { ideal: cam.IDEAL_HEIGHT },
    },
  });
  video.srcObject = stream;
  await video.play();
}

function explainCameraError(err) {
  switch (err.name) {
    case "NotAllowedError":
    case "SecurityError":
      showError(
        "Necesitamos tu cámara 📷",
        "Se negó el permiso para usar la cámara. Toca el ícono de candado o de cámara en la barra " +
          "de direcciones, permite el acceso a la cámara y recarga la página. En iPhone: " +
          "Ajustes → Safari → Cámara → Permitir."
      );
      break;
    case "NotFoundError":
    case "OverconstrainedError":
      showError("No encontramos una cámara", "Este dispositivo no tiene cámara frontal disponible.");
      break;
    case "NotReadableError":
      showError("La cámara está ocupada", "Cierra otras apps que usen la cámara y recarga la página.");
      break;
    case "InsecureContext":
      showError("Se necesita HTTPS", "Abre el filtro desde su enlace https:// para poder usar la cámara.");
      break;
    default:
      showError("No se pudo iniciar la cámara", err.message || String(err));
  }
}

// ---------- Depuración visual (solo con ?debug=1) ----------
// Contornos de ojos, cejas, labios y cara con los landmarks suavizados (lo que sigue la
// máscara) y puntos blancos con los landmarks crudos de MediaPipe.
function createContours() {
  const segments = [];
  const color = new THREE.Color();
  const colors = [];
  for (const [name, hex] of Object.entries(CONFIG.DEBUG_CONTOURS)) {
    color.setHex(hex);
    for (const { start, end } of FaceLandmarker[`FACE_LANDMARKS_${name}`]) {
      segments.push(start, end);
      colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(segments.length * 3), 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  const lines = new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ vertexColors: true, depthTest: false, transparent: true }),
  );
  lines.frustumCulled = false;
  lines.renderOrder = 11;
  lines.visible = false;
  lines.userData.segments = segments;
  return lines;
}

function updateContours(lines, landmarks, toWorld) {
  const attr = lines.geometry.attributes.position;
  lines.userData.segments.forEach((idx, k) => toWorld(landmarks[idx], attr.array, k * 3));
  attr.needsUpdate = true;
}

function createLandmarkPoints() {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(NUM_MESH_POINTS * 3);
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    color: CONFIG.DEBUG_POINT_COLOR,
    size: CONFIG.DEBUG_POINT_SIZE,
    sizeAttenuation: false,
    depthTest: false, // siempre encima de la máscara
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.renderOrder = 10;
  points.visible = false;
  return points;
}

function updateLandmarkPoints(points, landmarks, toWorld) {
  const attr = points.geometry.attributes.position;
  const n = Math.min(landmarks.length, NUM_MESH_POINTS);
  for (let i = 0; i < n; i++) toWorld(landmarks[i], attr.array, i * 3);
  points.geometry.setDrawRange(0, n);
  attr.needsUpdate = true;
}

// ---------- Sonido ----------
// Los navegadores no permiten audio sin interacción: el primer toque (en cualquier parte
// o en el botón) desbloquea el audio y lo enciende.
function setupAudio() {
  const refresh = () => {
    ui.sound.textContent = isMuted() ? "🔇" : "🔊";
    ui.sound.setAttribute("aria-label", isMuted() ? "Activar sonido" : "Silenciar");
  };
  const enable = async () => {
    if (!(await unlockAudio())) return;
    setMuted(false);
    refresh();
  };
  const firstTouch = (e) => {
    window.removeEventListener("pointerup", firstTouch, true);
    if (e.target !== ui.sound) enable(); // si fue el botón, lo maneja su "click"
  };
  window.addEventListener("pointerup", firstTouch, true);
  ui.sound.addEventListener("click", () => {
    if (!isUnlocked()) return enable();
    setMuted(!isMuted());
    refresh();
  });
  refresh();
}

// ---------- Depuración (?debug=1) ----------
// Barra de 0 a 1 con el umbral marcado: "██████|···"
function meter(value, threshold, width = 14) {
  const fill = Math.round(Math.min(Math.max(value, 0), 1) * width);
  const mark = Math.round(threshold * width);
  let s = "";
  for (let i = 0; i < width; i++) s += i === mark ? "|" : i < fill ? "█" : "·";
  return s;
}

function createDebugPanel(tracker, gestures) {
  if (!DEBUG) return () => {};
  show(ui.debug, true);
  let frames = 0;
  let fps = 0;
  let last = performance.now();
  return (face) => {
    frames++;
    const now = performance.now();
    if (now - last >= 500) {
      fps = (frames * 1000) / (now - last);
      frames = 0;
      last = now;
    }
    const lines = [
      `fps ${fps.toFixed(0)} · ${tracker.delegate}`,
      `video ${video.videoWidth}×${video.videoHeight}`,
      `cara ${face ? `sí (${face.landmarks.length} pts)` : "no"}`,
      `suavizado ${tracker.smoothing.enabled ? "sí" : "no"} · temblor px/cuadro: ` +
        `crudo ${tracker.jitter.raw.toFixed(2)} → ${tracker.jitter.smooth.toFixed(2)}`,
      "",
    ];
    for (const [name, { threshold }] of Object.entries(CONFIG.GESTURES)) {
      const g = gestures.state[name];
      lines.push(`${name.padEnd(11)} ${g.value.toFixed(2)} ${meter(g.value, threshold)} ×${g.count}`);
    }
    lines.push("", "líneas = suavizado · puntos = crudo", "teclas: B pétalos · P paleta · S suavizado");
    ui.debug.textContent = lines.join("\n");
  };
}

// ---------- Arranque ----------
async function main() {
  setupAudio();

  // La cámara, el modelo y la malla se cargan en paralelo.
  const view = createScene(canvas, video);
  const trackerPromise = createFaceTracker();
  // Con la plantilla o la guía se dibuja la malla completa (también sobre ojos y boca).
  const maskPromise = createMask(view.scene, view.renderer, MASK_TEXTURES,
    !STATIC_TEXTURE && CONFIG.MASK_CUT_HOLES);
  const effectsPromise = maskPromise.then((mask) =>
    createEffects({ scene: view.scene, renderer: view.renderer, mask })
  );
  // Los errores se manejan abajo, después de la cámara.
  trackerPromise.catch(() => {});
  effectsPromise.catch(() => {});
  try {
    await startCamera();
  } catch (err) {
    console.error("[main] cámara:", err);
    explainCameraError(err);
    return;
  }

  let tracker;
  try {
    tracker = await trackerPromise;
  } catch (err) {
    console.error("[main] MediaPipe:", err);
    showError("No se pudo cargar el detector facial", "Revisa tu conexión a internet y recarga la página.");
    return;
  }

  let mask;
  let effects;
  try {
    [mask, effects] = await Promise.all([maskPromise, effectsPromise]);
  } catch (err) {
    console.error("[main] máscara:", err);
    showError("No se pudo cargar la máscara", "Recarga la página para intentarlo de nuevo.");
    return;
  }
  show(ui.loading, false);
  show(ui.hint, true);
  view.resize(); // el video ya tiene tamaño real

  tracker.smoothing.enabled = SMOOTH && CONFIG.SMOOTHING.enabled;
  const gestures = createGestureDetector();
  const points = DEBUG ? createLandmarkPoints() : null;
  const contours = DEBUG ? createContours() : null;
  if (points) view.scene.add(points, contours);
  const updateDebug = createDebugPanel(tracker, gestures);
  if (DEBUG) {
    // Disparar los efectos con el teclado, sin hacer el gesto; S alterna el suavizado.
    window.addEventListener("keydown", (e) => {
      const t = performance.now() / 1000;
      if (e.key === "b") effects.trigger("jawOpen", t);
      if (e.key === "p") effects.trigger("browInnerUp", t);
      if (e.key === "s") tracker.smoothing.enabled = !tracker.smoothing.enabled;
    });
  }

  function frame(timeMs) {
    const t = timeMs / 1000;
    const face = tracker.detect(video, timeMs);
    if (face) {
      mask.update(face.landmarks, view.landmarkToWorld);
      for (const gesture of gestures.update(face.blendshapes, t)) effects.trigger(gesture, t);
      if (points) {
        updateLandmarkPoints(points, face.raw, view.landmarkToWorld);
        updateContours(contours, face.landmarks, view.landmarkToWorld);
      }
    } else {
      mask.hide();
      gestures.reset();
    }
    effects.update(t, face ? face.landmarks : null, view.landmarkToWorld);
    if (points) points.visible = contours.visible = !!face;
    show(ui.noFace, !face);
    updateDebug(face);
    view.render();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

main();
