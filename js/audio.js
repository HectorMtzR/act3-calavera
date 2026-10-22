// Sonidos con Web Audio API.
// Si CONFIG.SOUNDS trae la ruta de un archivo, se usa ese archivo; si no (o si falla),
// se usa un sonido sintetizado de SYNTH, si existe.
import { CONFIG } from "./config.js";

let ctx = null;
let master = null;
let muted = true;
const files = {}; // nombre -> AudioBuffer cargado

// ---------- Desbloqueo y volumen ----------

/** Debe llamarse dentro de un gesto del usuario (los navegadores bloquean el audio antes). */
export async function unlockAudio() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = muted ? 0 : 1;
    master.connect(ctx.destination);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) ctx.suspend();
      else ctx.resume();
    });
    loadFiles();
  }
  if (ctx.state === "suspended") await ctx.resume();
  return true;
}

export function isUnlocked() {
  return !!ctx;
}

export function setMuted(value) {
  muted = value;
  if (master) master.gain.setTargetAtTime(muted ? 0 : 1, ctx.currentTime, 0.05);
}

export function isMuted() {
  return muted;
}

async function loadFiles() {
  for (const [name, url] of Object.entries(CONFIG.SOUNDS)) {
    if (!url) continue;
    try {
      const data = await fetch(url).then((r) => {
        if (!r.ok) throw new Error(r.status);
        return r.arrayBuffer();
      });
      files[name] = await ctx.decodeAudioData(data);
    } catch (err) {
      console.warn(`[audio] no se pudo cargar ${url}`, err);
    }
  }
}

// ---------- Reproducción ----------

function out(volume) {
  const g = ctx.createGain();
  g.gain.value = volume;
  g.connect(master);
  return g;
}

function playBuffer(buffer, volume) {
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(out(volume));
  src.start();
  return src;
}

/** Reproduce un efecto por nombre ("petals", "palette"…). */
export function playSound(name) {
  if (!ctx || muted) return;
  if (files[name]) playBuffer(files[name], CONFIG.EFFECT_VOLUME);
  else SYNTH[name]?.(ctx.currentTime, out(CONFIG.EFFECT_VOLUME));
}

// ---------- Sonidos sintetizados (respaldo sin archivos) ----------

let noiseCache = null;
function whiteNoise() {
  if (!noiseCache) {
    noiseCache = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const d = noiseCache.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  return noiseCache;
}

/** Campana: parcial fundamental + parcial inarmónico (2.76×), con caída exponencial. */
function bell(t, freq, gain, decay, dest, type = "sine") {
  for (const [mult, g] of [[1, 1], [2.76, 0.35]]) {
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.value = freq * mult;
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, t);
    env.gain.exponentialRampToValueAtTime(gain * g, t + 0.008);
    env.gain.exponentialRampToValueAtTime(0.0001, t + decay / mult);
    osc.connect(env).connect(dest);
    osc.start(t);
    osc.stop(t + decay + 0.05);
  }
}

/** Viento ligero: ruido con filtro pasabanda que sube y baja. */
function wind(t, duration, gain, dest) {
  const noise = ctx.createBufferSource();
  noise.buffer = whiteNoise();
  noise.loop = true;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.Q.value = 0.8;
  bp.frequency.setValueAtTime(500, t);
  bp.frequency.linearRampToValueAtTime(1400, t + duration * 0.4);
  bp.frequency.linearRampToValueAtTime(700, t + duration);
  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, t);
  env.gain.exponentialRampToValueAtTime(gain, t + duration * 0.35);
  env.gain.exponentialRampToValueAtTime(0.0001, t + duration);
  noise.connect(bp).connect(env).connect(dest);
  noise.start(t);
  noise.stop(t + duration + 0.05);
}

// Escala pentatónica (do mayor) en la octava 6: siempre suena consonante.
const PENTATONIC = [1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0];

const SYNTH = {
  /** Lluvia de pétalos: campanitas al azar sobre un soplo de viento. */
  petals(t, dest) {
    wind(t, 2.0, 0.18, dest);
    let at = t;
    for (let i = 0; i < 9; i++) {
      const f = PENTATONIC[Math.floor(Math.random() * PENTATONIC.length)];
      bell(at, f, 0.12 + Math.random() * 0.06, 1.2 + Math.random() * 0.6, dest);
      at += 0.07 + Math.random() * 0.16;
    }
  },

  /** Cambio de paleta: brillo corto de dos notas ascendentes. */
  palette(t, dest) {
    bell(t, 784.0, 0.16, 0.7, dest, "triangle");
    bell(t + 0.09, 1174.7, 0.14, 0.9, dest, "triangle");
  },
};
