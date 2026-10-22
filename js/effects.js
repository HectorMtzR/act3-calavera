// Efectos de los gestos: lluvia de pétalos de cempasúchil (boca abierta) y cambio de
// paleta de la calavera (cejas arriba).
import * as THREE from "three";
import { CONFIG } from "./config.js";
import { playSound } from "./audio.js";

// Landmarks de MediaPipe usados por los efectos.
const LIP_TOP = 13;     // centro del labio superior (interior)
const LIP_BOTTOM = 14;  // centro del labio inferior (interior)
const FOREHEAD = 10;
const CHIN = 152;
const EYE_OUTER_R = 33;
const EYE_OUTER_L = 263;

const rand = (min, max) => min + Math.random() * (max - min);
const smoothstep = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));

// ---------- Pétalos ----------

const petalVertex = /* glsl */ `
  attribute float aSize;
  attribute float aAngle;
  attribute float aFlip;   // cos del giro en 3D: 1 de frente, 0 de canto, <0 por detrás
  attribute float aAlpha;
  attribute vec3 aTint;
  uniform float uPixelRatio;
  varying float vAngle;
  varying float vFlip;
  varying float vAlpha;
  varying vec3 vTint;
  void main() {
    vAngle = aAngle;
    vFlip = aFlip;
    vAlpha = aAlpha;
    vTint = aTint;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uPixelRatio;
  }
`;

const petalFragment = /* glsl */ `
  uniform sampler2D uTex;
  varying float vAngle;
  varying float vFlip;
  varying float vAlpha;
  varying vec3 vTint;
  void main() {
    if (vAlpha <= 0.0) discard;
    // Girar el sprite y angostarlo según el giro en 3D (el pétalo "aletea" al caer).
    vec2 p = gl_PointCoord - 0.5;
    float c = cos(vAngle), s = sin(vAngle);
    p = mat2(c, s, -s, c) * p;
    p.x /= max(abs(vFlip), 0.15);
    vec2 uv = p + 0.5;
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) discard;
    vec4 t = texture2D(uTex, vec2(uv.x, 1.0 - uv.y));
    float a = t.a * vAlpha;
    if (a < 0.02) discard;
    float back = vFlip < 0.0 ? 0.78 : 1.0;   // el revés del pétalo, un poco más oscuro
    gl_FragColor = vec4(t.rgb * vTint * back, a);
    #include <colorspace_fragment>
  }
`;

function createPetals(scene, renderer, texture, max) {
  const geometry = new THREE.BufferGeometry();
  const attr = (name, size) => {
    const a = new THREE.BufferAttribute(new Float32Array(max * size), size).setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute(name, a);
    return a.array;
  };
  const pos = attr("position", 3);
  const size = attr("aSize", 1);
  const angle = attr("aAngle", 1);
  const flip = attr("aFlip", 1);
  const alpha = attr("aAlpha", 1);
  const tint = attr("aTint", 3);

  const material = new THREE.ShaderMaterial({
    uniforms: { uTex: { value: texture }, uPixelRatio: { value: renderer.getPixelRatio() } },
    vertexShader: petalVertex,
    fragmentShader: petalFragment,
    transparent: true,
    depthTest: false, // siempre delante de la máscara
    depthWrite: false,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.renderOrder = 5;
  points.visible = false;
  scene.add(points);

  // Estado por pétalo (JS); los atributos se copian al GPU cada cuadro.
  const vel = new Float32Array(max * 2);
  const age = new Float32Array(max);
  const life = new Float32Array(max);  // 0 = libre
  const spin = new Float32Array(max);
  const flipSpeed = new Float32Array(max);
  const phase = new Float32Array(max);
  const swayFreq = new Float32Array(max);
  let next = 0;

  /** Agrega un pétalo en (x, y) mundo con velocidad (vx, vy); unidades en px. */
  function spawn(x, y, vx, vy, px, lifetime) {
    const i = next;
    next = (next + 1) % max;
    pos[i * 3] = x;
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = 0;
    vel[i * 2] = vx;
    vel[i * 2 + 1] = vy;
    size[i] = px;
    age[i] = 0;
    life[i] = lifetime;
    angle[i] = rand(0, Math.PI * 2);
    spin[i] = rand(-3, 3);
    flipSpeed[i] = rand(2, 6);
    phase[i] = rand(0, Math.PI * 2);
    swayFreq[i] = rand(1.5, 3.0);
    // De amarillo cempasúchil a naranja intenso.
    const k = Math.random();
    tint[i * 3] = 1;
    tint[i * 3 + 1] = 1 - 0.22 * k;
    tint[i * 3 + 2] = 1 - 0.45 * k;
  }

  /** Avanza la física. `scale` = ancho de cara en px (gravedad, balanceo y velocidad). */
  function update(dt, scale) {
    const P = CONFIG.PETALS;
    const g = P.gravity * scale;
    const terminal = P.terminal * scale;
    const sway = P.sway * scale;
    let alive = false;
    for (let i = 0; i < max; i++) {
      if (life[i] <= 0) {
        alpha[i] = 0;
        continue;
      }
      age[i] += dt;
      if (age[i] >= life[i]) {
        life[i] = 0;
        alpha[i] = 0;
        continue;
      }
      alive = true;
      // Gravedad suave con velocidad terminal y freno lateral (resistencia del aire).
      vel[i * 2 + 1] = Math.max(vel[i * 2 + 1] - g * dt, -terminal);
      vel[i * 2] *= Math.exp(-1.5 * dt);
      const swayV = sway * Math.cos(swayFreq[i] * age[i] + phase[i]);
      pos[i * 3] += (vel[i * 2] + swayV) * dt;
      pos[i * 3 + 1] += vel[i * 2 + 1] * dt;
      angle[i] += spin[i] * dt;
      flip[i] = Math.cos(flipSpeed[i] * age[i] + phase[i]);
      // Aparece en 0.15 s y se desvanece en los últimos 0.5 s.
      alpha[i] = Math.min(smoothstep(age[i] / 0.15), smoothstep((life[i] - age[i]) / 0.5));
    }
    for (const name of ["position", "aSize", "aAngle", "aFlip", "aAlpha", "aTint"]) {
      geometry.attributes[name].needsUpdate = true;
    }
    points.visible = alive;
    material.uniforms.uPixelRatio.value = renderer.getPixelRatio();
  }

  return { spawn, update };
}

// ---------- Efectos ----------

/**
 * @param scene, renderer  de three.js
 * @param mask   resultado de createMask (usa mask.uniforms.uMix)
 */
export async function createEffects({ scene, renderer, mask }) {
  const P = CONFIG.PETALS;
  const texture = await new THREE.TextureLoader().loadAsync(P.sprite);
  texture.colorSpace = THREE.SRGBColorSpace;
  const petals = createPetals(scene, renderer, texture, P.count + P.mouth * 2);

  let rainStart = -Infinity;
  let rainSpawned = 0;
  let lastTime = null;
  let mixFrom = 0;
  let mixTo = 0;
  let mixStart = -Infinity;

  // Geometría de la cara en el mundo (se actualiza cuando hay rostro).
  const face = { cx: 0, topY: 0, mouthX: 0, mouthY: 0, upX: 0, upY: 1, scale: 150, valid: false };
  const tmp = new Float32Array(3);
  const world = (lm, toWorld) => (toWorld(lm, tmp, 0), [tmp[0], tmp[1]]);

  function readFace(landmarks, toWorld) {
    const [tx, ty] = world(landmarks[LIP_TOP], toWorld);
    const [bx, by] = world(landmarks[LIP_BOTTOM], toWorld);
    const [fx, fy] = world(landmarks[FOREHEAD], toWorld);
    const [cx, cy] = world(landmarks[CHIN], toWorld);
    const [rx, ry] = world(landmarks[EYE_OUTER_R], toWorld);
    const [lx, ly] = world(landmarks[EYE_OUTER_L], toWorld);
    face.mouthX = (tx + bx) / 2;
    face.mouthY = (ty + by) / 2;
    const ux = fx - cx;
    const uy = fy - cy;
    const len = Math.hypot(ux, uy) || 1;
    face.upX = ux / len;
    face.upY = uy / len;
    face.cx = (fx + cx) / 2;
    face.topY = fy; // parte alta de la frente
    face.scale = Math.hypot(lx - rx, ly - ry);
    face.valid = true;
  }

  function spawnRain(n) {
    const s = face.scale;
    for (let k = 0; k < n; k++) {
      petals.spawn(
        face.cx + rand(-P.spread, P.spread) * s,
        face.topY + rand(...P.height) * s,
        rand(-0.2, 0.2) * s,
        rand(-0.6, -0.2) * s,
        rand(...P.size) * s,
        rand(0.85, 1.25) * P.duration,
      );
    }
  }

  function spawnFromMouth() {
    const s = face.scale;
    for (let k = 0; k < P.mouth; k++) {
      // Hacia "arriba de la cara", abiertos en abanico a los lados.
      const a = rand(-1.0, 1.0);
      const dx = face.upX * Math.cos(a) - face.upY * Math.sin(a);
      const dy = face.upX * Math.sin(a) + face.upY * Math.cos(a);
      const v = rand(...P.mouthSpeed) * s;
      petals.spawn(face.mouthX, face.mouthY, dx * v, dy * v, rand(...P.size) * s * 0.8, rand(1.2, 1.7));
    }
  }

  /** Dispara el efecto asociado a un gesto (nombre del blendshape). */
  function trigger(gesture, timeSec) {
    if (gesture === "jawOpen") {
      rainStart = timeSec;
      rainSpawned = 0;
      if (face.valid) spawnFromMouth();
      playSound("petals");
    } else if (gesture === "browInnerUp") {
      mixFrom = mask.uniforms.uMix.value;
      mixTo = mixTo > 0.5 ? 0 : 1;
      mixStart = timeSec;
      playSound("palette");
    }
  }

  /** Avanza los efectos. `landmarks` puede ser null si no hay rostro. */
  function update(timeSec, landmarks, toWorld) {
    const dt = lastTime === null ? 0 : Math.min(timeSec - lastTime, 0.1);
    lastTime = timeSec;
    if (landmarks) readFace(landmarks, toWorld);

    // Lluvia: los pétalos aparecen repartidos en la primera mitad de la duración.
    const spawnWindow = P.duration * 0.5;
    const tr = timeSec - rainStart;
    if (tr >= 0 && tr < spawnWindow + dt && face.valid) {
      const due = Math.min(P.count, Math.round((P.count * Math.min(tr, spawnWindow)) / spawnWindow));
      spawnRain(due - rainSpawned);
      rainSpawned = due;
    }
    petals.update(dt, face.scale);

    // Cambio de paleta con curva suave.
    const k = smoothstep((timeSec - mixStart) / CONFIG.PALETTE_TRANSITION);
    mask.uniforms.uMix.value = mixFrom + (mixTo - mixFrom) * k;
  }

  return { trigger, update };
}
