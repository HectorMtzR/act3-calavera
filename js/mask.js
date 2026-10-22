// Malla facial three.js: triángulos y UVs fijos de la malla canónica de MediaPipe,
// posiciones actualizadas cada cuadro con los landmarks detectados.
// El shader mezcla dos texturas (paleta principal y alternativa) con `uMix`.
import * as THREE from "three";
import { FaceLandmarker } from "@mediapipe/tasks-vision";
import { CONFIG } from "./config.js";

/**
 * Lee el OBJ canónico. En este archivo los índices de UV (`vt`) no coinciden con los de
 * vértice (`v`), pero cada vértice usa siempre la misma UV, así que se reordenan las UVs
 * por índice de vértice: el vértice i de la malla = landmark i de MediaPipe.
 */
function parseCanonicalObj(text) {
  const vts = [];
  const faces = [];
  let numVerts = 0;
  for (const line of text.split("\n")) {
    const p = line.trim().split(/\s+/);
    if (p[0] === "v") numVerts++;
    else if (p[0] === "vt") vts.push([+p[1], +p[2]]);
    else if (p[0] === "f") faces.push(p.slice(1, 4).map((c) => c.split("/").map((n) => +n - 1)));
  }

  const uvs = new Float32Array(numVerts * 2);
  const indices = new Uint16Array(faces.length * 3);
  faces.forEach((face, f) => {
    face.forEach(([vi, ti], k) => {
      indices[f * 3 + k] = vi;
      uvs[vi * 2] = vts[ti][0];
      uvs[vi * 2 + 1] = vts[ti][1];
    });
  });
  return { numVerts, uvs, indices };
}

/** Encadena las aristas de un conjunto de conexiones de MediaPipe en contornos cerrados. */
function chainLoops(connections) {
  const adj = new Map();
  const link = (a, b) => (adj.get(a) ?? adj.set(a, []).get(a)).push(b);
  for (const { start, end } of connections) {
    link(start, end);
    link(end, start);
  }
  const seen = new Set();
  const loops = [];
  for (const s of adj.keys()) {
    if (seen.has(s)) continue;
    const loop = [];
    let prev = -1;
    let cur = s;
    while (cur !== undefined && !seen.has(cur)) {
      seen.add(cur);
      loop.push(cur);
      const next = adj.get(cur).find((n) => n !== prev && !seen.has(n));
      prev = cur;
      cur = next;
    }
    loops.push(loop);
  }
  return loops;
}

function uvArea(loop, uvs) {
  let a = 0;
  for (let k = 0; k < loop.length; k++) {
    const i = loop[k];
    const j = loop[(k + 1) % loop.length];
    a += uvs[i * 2] * uvs[j * 2 + 1] - uvs[j * 2] * uvs[i * 2 + 1];
  }
  return Math.abs(a / 2);
}

/**
 * La malla canónica está triangulada también sobre los ojos y el interior de la boca.
 * Esos triángulos son exactamente los que tienen sus 3 vértices sobre un mismo contorno
 * (ojo izquierdo, ojo derecho o interior de los labios); se quitan del índice.
 */
function removeHoleTriangles(indices, uvs) {
  const [inner] = chainLoops(FaceLandmarker.FACE_LANDMARKS_LIPS).sort((a, b) => uvArea(a, uvs) - uvArea(b, uvs));
  const holes = [
    new Set(chainLoops(FaceLandmarker.FACE_LANDMARKS_LEFT_EYE)[0]),
    new Set(chainLoops(FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE)[0]),
    new Set(inner),
  ];
  const kept = [];
  for (let f = 0; f < indices.length; f += 3) {
    const tri = [indices[f], indices[f + 1], indices[f + 2]];
    if (!holes.some((h) => tri.every((v) => h.has(v)))) kept.push(...tri);
  }
  console.info(`[mask] huecos de ojos y boca: ${(indices.length - kept.length) / 3} triángulos fuera`);
  return new Uint16Array(kept);
}

async function loadTexture(url, renderer) {
  const tex = await new THREE.TextureLoader().loadAsync(url);
  tex.colorSpace = THREE.SRGBColorSpace;
  // Mipmaps + filtrado trilineal y anisotrópico: nítida de cerca y sin parpadeo de lejos.
  tex.generateMipmaps = true;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return tex;
}

/** Carga la textura; si no existe todavía, usa la plantilla UV. */
async function loadTextureOrTemplate(url, renderer) {
  try {
    return await loadTexture(url, renderer);
  } catch (err) {
    console.warn(`[mask] no se pudo cargar ${url}; se usa la plantilla UV`, err);
    return loadTexture(CONFIG.UV_TEMPLATE, renderer);
  }
}

const vertexShader = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  uniform sampler2D uMaskA;  // paleta principal
  uniform sampler2D uMaskB;  // paleta alternativa
  uniform float uMix;        // 0 = A, 1 = B
  varying vec2 vUv;

  void main() {
    vec4 c = mix(texture2D(uMaskA, vUv), texture2D(uMaskB, vUv), uMix);
    // Los huecos de ojos y boca vienen en el alfa de la textura.
    if (c.a < 0.01) discard;
    gl_FragColor = c;
    #include <colorspace_fragment>
  }
`;

/**
 * Crea la máscara y la agrega a la escena (oculta hasta que haya rostro).
 * `textures`: { a, b } rutas de las dos paletas (pueden ser la misma).
 * `cutHoles`: quitar los triángulos de ojos y boca (con la plantilla o la guía conviene verlos).
 * Devuelve { mesh, uniforms, update(landmarks, landmarkToWorld), hide() }.
 */
export async function createMask(scene, renderer, textures, cutHoles = CONFIG.MASK_CUT_HOLES) {
  const [objText, texA, texB] = await Promise.all([
    fetch(CONFIG.FACE_MODEL).then((r) => {
      if (!r.ok) throw new Error(`No se pudo cargar ${CONFIG.FACE_MODEL} (${r.status})`);
      return r.text();
    }),
    loadTextureOrTemplate(textures.a, renderer),
    textures.b === textures.a ? null : loadTextureOrTemplate(textures.b, renderer),
  ]);
  const { numVerts, uvs, indices: allIndices } = parseCanonicalObj(objText);
  const indices = cutHoles ? removeHoleTriangles(allIndices, uvs) : allIndices;

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(numVerts * 3);
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));
  geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));

  const uniforms = {
    uMaskA: { value: texA },
    uMaskB: { value: texB ?? texA },
    uMix: { value: 0 },
  };

  const material = new THREE.ShaderMaterial({
    uniforms,
    vertexShader,
    fragmentShader,
    transparent: true,
    // El espejo invierte el sentido de los triángulos; se dibujan ambas caras.
    side: THREE.DoubleSide,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false; // las posiciones cambian cada cuadro
  mesh.visible = false;
  scene.add(mesh);

  function update(landmarks, landmarkToWorld) {
    // Los 10 landmarks extra del iris (468–477) no forman parte de la malla.
    for (let i = 0; i < numVerts; i++) landmarkToWorld(landmarks[i], positions, i * 3);
    geometry.attributes.position.needsUpdate = true;
    mesh.visible = true;
  }

  function hide() {
    mesh.visible = false;
  }

  return { mesh, uniforms, update, hide };
}
