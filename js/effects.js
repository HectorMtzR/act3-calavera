// Efectos de los gestos: lluvia de pétalos (boca abierta) y cambio de paleta (cejas arriba).
// Se implementan en la Fase 5; por ahora solo se registra el gesto.
import { playSound } from "./audio.js";

/**
 * @param scene, renderer  de three.js
 * @param mask   resultado de createMask (usa mask.uniforms.uMix)
 */
export async function createEffects({ scene, renderer, mask }) {
  /** Dispara el efecto asociado a un gesto (nombre del blendshape). */
  function trigger(gesture, timeSec) {
    console.debug(`[effects] ${gesture} @ ${timeSec.toFixed(2)} s`);
    if (gesture === "jawOpen") playSound("petals");
    else if (gesture === "browInnerUp") playSound("palette");
  }

  /** Avanza los efectos. `landmarks` puede ser null si no hay rostro. */
  function update(timeSec, landmarks, toWorld) {}

  return { trigger, update };
}
