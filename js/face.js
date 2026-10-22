// MediaPipe Face Landmarker: carga del modelo, detección por cuadro y suavizado de landmarks.
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { CONFIG } from "./config.js";

const NUM_POINTS = 478; // 468 de la cara + 10 del iris

async function createLandmarker(vision, delegate) {
  const mp = CONFIG.MEDIAPIPE;
  return FaceLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: mp.MODEL_URL, delegate },
    runningMode: "VIDEO",
    numFaces: mp.NUM_FACES,
    outputFaceBlendshapes: true,
    minFaceDetectionConfidence: mp.MIN_DETECTION_CONFIDENCE,
    minTrackingConfidence: mp.MIN_TRACKING_CONFIDENCE,
  });
}

/**
 * Filtro One Euro (Casiez, Roussel y Vogel, 2012), uno por coordenada.
 * Con movimiento lento la frecuencia de corte baja (quita el temblor); con movimiento
 * rápido sube en proporción a la velocidad (evita el retraso).
 */
function createOneEuro(size, { minCutoff, beta, dCutoff = 1.0 }) {
  const x = new Float32Array(size);   // valor filtrado
  const dx = new Float32Array(size);  // derivada filtrada
  let tPrev = null;
  const alpha = (cutoff, dt) => 1 / (1 + 1 / (2 * Math.PI * cutoff * dt));

  function filter(values, t) {
    if (tPrev === null) {
      x.set(values);
      dx.fill(0);
      tPrev = t;
      return x;
    }
    const dt = t - tPrev;
    if (dt <= 0) return x;
    tPrev = t;
    const aD = alpha(dCutoff, dt);
    for (let i = 0; i < size; i++) {
      dx[i] += aD * ((values[i] - x[i]) / dt - dx[i]);
      x[i] += alpha(minCutoff + beta * Math.abs(dx[i]), dt) * (values[i] - x[i]);
    }
    return x;
  }

  return { filter, reset: () => (tPrev = null) };
}

/**
 * Crea el detector. Intenta con GPU y, si falla (p. ej. algunos iPhone), usa CPU.
 * Devuelve { delegate, smoothing, jitter, detect(video, timeMs) }.
 * detect() regresa null si no hay rostro; si el video no tiene un cuadro nuevo, repite el último.
 * El resultado trae `landmarks` (suavizados si smoothing.enabled), `raw` y `blendshapes`.
 */
export async function createFaceTracker() {
  const vision = await FilesetResolver.forVisionTasks(CONFIG.MEDIAPIPE.WASM_URL);

  let landmarker;
  let delegate = "GPU";
  try {
    landmarker = await createLandmarker(vision, "GPU");
  } catch (err) {
    console.warn("[face] GPU no disponible, usando CPU:", err);
    delegate = "CPU";
    landmarker = await createLandmarker(vision, "CPU");
  }

  // El filtro trabaja en píxeles del video para que `beta` no dependa de la resolución.
  const euro = createOneEuro(NUM_POINTS * 3, CONFIG.SMOOTHING);
  const buf = new Float32Array(NUM_POINTS * 3);
  const smoothed = Array.from({ length: NUM_POINTS }, () => ({ x: 0, y: 0, z: 0 }));
  const smoothing = { enabled: CONFIG.SMOOTHING.enabled };
  let wasEnabled = smoothing.enabled;

  // Temblor: desplazamiento medio por cuadro (px de video), promedio móvil.
  const jitter = { raw: 0, smooth: 0 };
  const prevRaw = new Float32Array(NUM_POINTS * 2);
  const prevSmooth = new Float32Array(NUM_POINTS * 2);
  let havePrev = false;

  let lastVideoTime = -1;
  let lastTimestamp = 0;
  let lastResult = null;

  function smooth(raw, w, h, tSec) {
    const n = Math.min(raw.length, NUM_POINTS);
    for (let i = 0; i < n; i++) {
      buf[i * 3] = raw[i].x * w;
      buf[i * 3 + 1] = raw[i].y * h;
      buf[i * 3 + 2] = raw[i].z * w;
    }
    const f = euro.filter(buf, tSec);
    for (let i = 0; i < n; i++) {
      smoothed[i].x = f[i * 3] / w;
      smoothed[i].y = f[i * 3 + 1] / h;
      smoothed[i].z = f[i * 3 + 2] / w;
    }
    return smoothed;
  }

  function measureJitter(raw, out, w, h) {
    const n = Math.min(raw.length, NUM_POINTS);
    let dr = 0;
    let ds = 0;
    for (let i = 0; i < n; i++) {
      const rx = raw[i].x * w, ry = raw[i].y * h, sx = out[i].x * w, sy = out[i].y * h;
      if (havePrev) {
        dr += Math.hypot(rx - prevRaw[i * 2], ry - prevRaw[i * 2 + 1]);
        ds += Math.hypot(sx - prevSmooth[i * 2], sy - prevSmooth[i * 2 + 1]);
      }
      prevRaw[i * 2] = rx;
      prevRaw[i * 2 + 1] = ry;
      prevSmooth[i * 2] = sx;
      prevSmooth[i * 2 + 1] = sy;
    }
    if (havePrev) {
      jitter.raw += 0.1 * (dr / n - jitter.raw);
      jitter.smooth += 0.1 * (ds / n - jitter.smooth);
    }
    havePrev = true;
  }

  function detect(video, timeMs) {
    if (video.readyState < 2) return null;
    // Solo procesar cuando el video tiene un cuadro nuevo.
    if (video.currentTime === lastVideoTime) return lastResult;
    lastVideoTime = video.currentTime;

    // MediaPipe exige marcas de tiempo estrictamente crecientes.
    const ts = Math.max(timeMs, lastTimestamp + 1);
    lastTimestamp = ts;

    const res = landmarker.detectForVideo(video, ts);
    if (!res.faceLandmarks || res.faceLandmarks.length === 0) {
      euro.reset();
      havePrev = false;
      lastResult = null;
      return null;
    }

    // Blendshapes como objeto { nombre: valor } para acceso directo.
    const blendshapes = {};
    const cats = res.faceBlendshapes?.[0]?.categories ?? [];
    for (const c of cats) blendshapes[c.categoryName] = c.score;

    const raw = res.faceLandmarks[0];
    if (smoothing.enabled !== wasEnabled) {
      euro.reset(); // al reactivarlo no arrastra el estado viejo
      wasEnabled = smoothing.enabled;
    }
    const w = video.videoWidth || 1;
    const h = video.videoHeight || 1;
    const landmarks = smoothing.enabled ? smooth(raw, w, h, ts / 1000) : raw;
    measureJitter(raw, landmarks, w, h);

    lastResult = { landmarks, raw, blendshapes };
    return lastResult;
  }

  return { delegate, smoothing, jitter, detect };
}
