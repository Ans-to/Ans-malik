/**
 * stage.ts — camera, projection and 3D type/wire drawing.
 *
 * There is exactly one camera for the whole film. Every scene happens inside
 * the same 3D world, which is what makes the cuts feel like one continuous
 * move instead of a slideshow.
 */

import { Frame, type RGB } from '../core/raster.ts';
import {
  clamp,
  cross,
  mat4,
  multiply,
  norm,
  perspective,
  lookAt,
  rotateAxis,
  sub,
  type Mat4,
  type Vec3,
  lerp,
} from '../core/math.ts';

export interface Projected {
  x: number;
  y: number;
  /** view-space distance from the camera */
  depth: number;
  ok: boolean;
}

export class Camera {
  eye: Vec3;
  target: Vec3;
  up: Vec3 = [0, 1, 0];
  roll = 0;
  fov = (48 * Math.PI) / 180;
  near = 0.05;
  far = 200;
  private vp: Mat4 = mat4();
  private w = 1280;
  private h = 720;

  constructor(eye: Vec3 = [0, 0, 6], target: Vec3 = [0, 0, 0]) {
    this.eye = eye;
    this.target = target;
  }

  resize(w: number, h: number): void {
    this.w = w;
    this.h = h;
  }

  update(): void {
    const forward = norm(sub(this.eye, this.target));
    const up = this.roll !== 0 ? rotateAxis(this.up, forward, this.roll) : this.up;
    const view = lookAt(this.eye, this.target, up);
    const proj = perspective(this.fov, this.w / this.h, this.near, this.far);
    this.vp = multiply(proj, view);
  }

  project(p: Vec3): Projected {
    const m = this.vp;
    const x = p[0], y = p[1], z = p[2];
    const cx = m[0] * x + m[4] * y + m[8] * z + m[12];
    const cy = m[1] * x + m[5] * y + m[9] * z + m[13];
    const cz = m[2] * x + m[6] * y + m[10] * z + m[14];
    const cw = m[3] * x + m[7] * y + m[11] * z + m[15];
    if (cw <= this.near) return { x: 0, y: 0, depth: cw, ok: false };
    const ndcX = cx / cw;
    const ndcY = cy / cw;
    return {
      x: (ndcX * 0.5 + 0.5) * this.w,
      y: (1 - (ndcY * 0.5 + 0.5)) * this.h,
      depth: cw,
      ok: Math.abs(ndcX) < 4 && Math.abs(ndcY) < 4,
    };
  }

  /** World units -> pixels at a given depth (for constant-width strokes). */
  scaleAt(depth: number): number {
    return (this.h * 0.5) / (Math.tan(this.fov * 0.5) * Math.max(1e-4, depth));
  }
}

/** Transform a point by euler angles (XYZ order). */
export function applyEuler(p: Vec3, r: Vec3): Vec3 {
  const [rx, ry, rz] = r;
  const cx = Math.cos(rx), sx = Math.sin(rx);
  const cy = Math.cos(ry), sy = Math.sin(ry);
  const cz = Math.cos(rz), sz = Math.sin(rz);
  let x = p[0], y = p[1] * cx - p[2] * sx, z = p[1] * sx + p[2] * cx;
  const x2 = x * cy + z * sy;
  const z2 = -x * sy + z * cy;
  x = x2; z = z2;
  return [x * cz - y * sz, x * sz + y * cz, z];
}

/* ------------------------------------------------------------- wireframes */

export interface Mesh {
  verts: Vec3[];
  edges: Array<[number, number]>;
}

export function drawMesh(
  frame: Frame,
  cam: Camera,
  mesh: Mesh,
  color: RGB,
  opts: {
    position?: Vec3;
    rotation?: Vec3;
    scale?: number;
    opacity?: number;
    weight?: number;
    /** fade with distance from the camera */
    fog?: number;
    /** 0..1 per-vertex jitter drive (glitch shards) */
    shatter?: number;
    seed?: number;
  } = {},
): void {
  const pos = opts.position ?? [0, 0, 0];
  const rot = opts.rotation ?? [0, 0, 0];
  const sc = opts.scale ?? 1;
  const op = opts.opacity ?? 1;
  const weight = opts.weight ?? 1.1;
  if (op <= 0.002) return;

  const world: Vec3[] = new Array(mesh.verts.length);
  for (let i = 0; i < mesh.verts.length; i++) {
    const v = mesh.verts[i];
    let p: Vec3 = [v[0] * sc, v[1] * sc, v[2] * sc];
    if (opts.shatter) {
      const s = opts.shatter;
      const seed = (opts.seed ?? 0) + i * 12.9898;
      p = [
        p[0] + Math.sin(seed) * s,
        p[1] + Math.cos(seed * 1.7) * s,
        p[2] + Math.sin(seed * 0.7) * s,
      ];
    }
    const r = applyEuler(p, rot);
    world[i] = [r[0] + pos[0], r[1] + pos[1], r[2] + pos[2]];
  }

  for (const [ia, ib] of mesh.edges) {
    const a = cam.project(world[ia]);
    const b = cam.project(world[ib]);
    if (!a.ok || !b.ok) continue;
    const depth = (a.depth + b.depth) * 0.5;
    const atten = clamp(1.2 - (depth - 4) * 0.03 * (opts.fog ?? 1));
    const inten = op * atten;
    if (inten <= 0.004) continue;
    const px = Math.max(0.6, weight * cam.scaleAt(depth) / 90);
    frame.line(a.x, a.y, b.x, b.y, color, px, inten);
  }
}

/** Perspective floor grid — the single best "depth cue" in motion graphics. */
export function drawGrid(
  frame: Frame,
  cam: Camera,
  opts: {
    y?: number;
    extent?: number;
    step?: number;
    color: RGB;
    opacity?: number;
    fadeRadius?: number;
  },
): void {
  const y = opts.y ?? -1.2;
  const extent = opts.extent ?? 14;
  const step = opts.step ?? 0.5;
  const col = opts.color;
  const op = opts.opacity ?? 0.5;
  const fade = opts.fadeRadius ?? 9;

  for (let z = -extent; z <= extent; z += step) {
    for (let x = -extent; x < extent; x += step) {
      const a = cam.project([x, y, z]);
      const b = cam.project([x + step, y, z]);
      if (!a.ok || !b.ok) continue;
      const d = a.depth;
      const att = clamp(1 - d / fade) ** 2 * op;
      if (att <= 0.004) continue;
      frame.line(a.x, a.y, b.x, b.y, col, Math.max(0.5, cam.scaleAt(d) / 900), att * 0.5);
    }
  }
  for (let x = -extent; x <= extent; x += step) {
    for (let z = -extent; z < extent; z += step) {
      const a = cam.project([x, y, z]);
      const b = cam.project([x, y, z + step]);
      if (!a.ok || !b.ok) continue;
      const d = a.depth;
      const att = clamp(1 - d / fade) ** 2 * op;
      if (att <= 0.004) continue;
      frame.line(a.x, a.y, b.x, b.y, col, Math.max(0.5, cam.scaleAt(d) / 900), att * 0.5);
    }
  }
}

/** Glowing particle field — cheap, and it sells camera motion beautifully. */
export function drawParticles(
  frame: Frame,
  cam: Camera,
  points: Vec3[],
  color: RGB,
  opts: { size?: number; opacity?: number; fog?: number } = {},
): void {
  const size = opts.size ?? 1.6;
  const op = opts.opacity ?? 0.7;
  for (const p of points) {
    const q = cam.project(p);
    if (!q.ok) continue;
    const att = clamp(1.25 - q.depth * 0.035 * (opts.fog ?? 1));
    if (att <= 0.01) continue;
    const r = size * (cam.scaleAt(q.depth) / 240);
    frame.glow(q.x, q.y, Math.max(1.2, r), color, op * att * 0.55, 2.2);
  }
}

export { lerp, cross };
