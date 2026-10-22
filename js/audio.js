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

// ---------- Sonidos sintetizados (respaldo sin archivos; Fase 5) ----------

const SYNTH = {};
