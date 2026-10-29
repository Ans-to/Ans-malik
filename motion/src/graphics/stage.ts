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
import { glyphFor, layout } from '../graphics/font.ts';

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

/* ------------------------------------------------------------------ 3D type */

export interface CharAnim {
  /** 0..1 visibility */
  opacity?: number;
  scale?: number;
  /** local offset in em units (x right, y up, z toward camera) */
  offset?: [number, number, number];
  rotZ?: number;
  /** extra additive glow for impacts */
  glow?: number;
  /** per-character tracking offset in em */
  track?: number;
}

export interface TextOptions {
  text: string;
  /** world height of one em (cap height) */
  size: number;
  position: Vec3;
  /** euler XYZ in radians */
  rotation?: Vec3;
  tracking?: number;
  align?: 'center' | 'left' | 'right';
  color: RGB;
  /** stroke width in pixels at depth 1 */
  weight?: number;
  opacity?: number;
  /** number of extruded wireframe slices along local +Z */
  extrusion?: number;
  extrusionDepth?: number;
  perChar?: (i: number, n: number) => CharAnim;
  /** multiplier for distance-based attenuation */
  fog?: number;
}

/** Transform a point by euler angles (XYZ order). */
function applyEuler(p: Vec3, r: Vec3): Vec3 {
  const [rx, ry, rz] = r;
  const cx = Math.cos(rx), sx = Math.sin(rx);
  const cy = Math.cos(ry), sy = Math.sin(ry);
  const cz = Math.cos(rz), sz = Math.sin(rz);
  // X
  let x = p[0], y = p[1] * cx - p[2] * sx, z = p[1] * sx + p[2] * cx;
  // Y
  const x2 = x * cy + z * sy;
  const z2 = -x * sy + z * cy;
  x = x2; z = z2;
  // Z
  const x3 = x * cz - y * sz;
  const y3 = x * sz + y * cz;
  return [x3, y3, z];
}

export function drawText(frame: Frame, cam: Camera, o: TextOptions): void {
  const tracking = o.tracking ?? 0.16;
  const weight = o.weight ?? 1.6;
  const rot = o.rotation ?? [0, 0, 0];
  const { chars, width } = layout(o.text, tracking);
  const n = chars.length;
  let originX = 0;
  if (o.align === 'center') originX = -width / 2;
  else if (o.align === 'right') originX = -width;

  const slices = o.extrusion ?? 1;
  const sliceGap = o.extrusionDepth ?? 0.02;
  const opacity = o.opacity ?? 1;
  if (opacity <= 0.002) return;

  for (let ci = 0; ci < n; ci++) {
    const c = chars[ci];
    if (c.ch === ' ') continue;
    const g = glyphFor(c.ch);
    const a = o.perChar ? o.perChar(ci, n) : {};
    const op = (a.opacity ?? 1) * opacity;
    if (op <= 0.002) continue;
    const s = a.scale ?? 1;
    const off = a.offset ?? [0, 0, 0];
    const rz = a.rotZ ?? 0;

    // glyph centre in em space (for scale/rotate about the letter's own centre)
    const cxc = originX + c.x + a.track! * 0 + c.w * 0.5 + (a.track ?? 0);
    for (let slice = 0; slice < slices; slice++) {
      const sliceFade = slices === 1 ? 1 : 0.9 - (slice / slices) * 0.72;
      for (const stroke of g.strokes) {
        const pts: Array<[number, number]> = [];
        let visible = true;
        for (const [gx, gy] of stroke) {
          // local em coords, origin bottom-left of glyph
          let lx = gx - c.w * 0.5;
          let ly = gy - 0.5;
          // per-char scale + spin about char centre
          const cs = Math.cos(rz), sn = Math.sin(rz);
          const rx2 = lx * cs - ly * sn;
          const ry2 = lx * sn + ly * cs;
          lx = rx2 * s;
          ly = ry2 * s;
          // to world: y up, z toward viewer
          const wx = originX + c.x + c.w * 0.5 + lx + off[0];
          const wy = ly + off[1];
          const wz = off[2] - slice * sliceGap;
          const world = applyEuler([wx * o.size, wy * o.size, wz * o.size], rot);
          const p = cam.project([
            world[0] + o.position[0],
            world[1] + o.position[1],
            world[2] + o.position[2],
          ]);
          if (!p.ok) {
            visible = false;
            break;
          }
          pts.push([p.x, p.y]);
        }
        if (!visible || pts.length < 2) continue;
        const depth = cam.project(
          ((): Vec3 => {
            const w = applyEuler(
              [(originX + c.x + c.w * 0.5) * o.size, (off[1]) * o.size, off[2] * o.size],
              rot,
            );
            return [w[0] + o.position[0], w[1] + o.position[1], w[2] + o.position[2]];
          })(),
        ).depth;
        const pxScale = cam.scaleAt(depth) / 55;
        const w = Math.max(0.75, weight * pxScale);
        const fog = o.fog ?? 1;
        const atten = clamp(1.15 - (depth - 4) * 0.02 * fog);
        const inten = op * atten * sliceFade * (1 + (a.glow ?? 0) * 2.2) * 0.85;
        if (inten <= 0.003) continue;
        frame.polyline(pts, o.color, w, inten);
      }
    }
  }
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
