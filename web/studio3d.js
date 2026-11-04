import * as THREE from 'three';
import {BokehPass} from 'three/addons/postprocessing/BokehPass.js';

/** Add three-point lighting, atmosphere and a depth-of-field pass to a scene. */
export function setupStudio(scene, camera, composer, palette) {
  if (!palette?.background) throw new Error('Provide a design-system palette');
  const key = new THREE.DirectionalLight('#FFE3B8', 3); key.position.set(4, 5, 5);
  const fill = new THREE.DirectionalLight('#A8C8E8', 1.3); fill.position.set(-5, 2, 3);
  const rim = new THREE.DirectionalLight('#D6E9F7', 5); rim.position.set(0, 4, -5);
  scene.add(key, fill, rim);
  scene.fog = new THREE.FogExp2(palette.background, 0.025);
  const bokeh = new BokehPass(scene, camera, {focus: 5, aperture: 0.00015, maxblur: 0.008});
  composer.addPass(bokeh);
  return {key, fill, rim, bokeh};
}
/** Deterministic procedural bump map and metal PBR material. */
export function studioMaterial(color, size = 128) {
  const data = new Uint8Array(size * size * 4);
  let state = 42;
  for (let i = 0; i < size * size; i++) {
    state = (1664525 * state + 1013904223) >>> 0;
    const v = state >>> 24;
    data.set([v, v, v, 255], i * 4);
  }
  const bumpMap = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  bumpMap.wrapS = bumpMap.wrapT = THREE.RepeatWrapping;
  bumpMap.needsUpdate = true;
  return new THREE.MeshStandardMaterial({color, roughness: 0.25, metalness: 0.8, bumpMap, bumpScale: 0.015});
}
