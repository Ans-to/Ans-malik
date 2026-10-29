/**
 * scene.ts — the film itself.
 *
 * One continuous camera move through one small 3D world, cut into five beats.
 * All timing is derived from the *analysed* soundtrack (beat grid + onset
 * envelope), so re-syncing the picture to new music is a re-render, not a
 * re-edit.
 */

import { Frame, type RGB } from './core/raster.ts';
import * as FX from './core/fx.ts';
import {
  clamp,
  lerp,
  mix3,
  noise1,
  smoothstep,
  smootherstep,
  type Vec3,
} from './core/math.ts';
import {
  easeInOutCubic,
  easeInOutExpo,
  easeOutBack,
  easeOutElastic,
  easeOutExpo,
  easeInCubic,
  spring,
  type Ease,
} from './core/easing.ts';
import { Camera, drawGrid, drawMesh, drawParticles, drawText, type CharAnim } from './graphics/stage.ts';
import { icosphere, morph, particleField, ring, type ShapeName } from './graphics/wire.ts';
import type { Analysis } from './audio/analyze.ts';

/* ------------------------------------------------------------------ palette */
export const C = {
  ice: [0.45, 0.95, 1.25] as RGB,
  cyan: [0.15, 0.75, 1.2] as RGB,
  magenta: [1.35, 0.22, 0.62] as RGB,
  blue: [0.22, 0.4, 1.3] as RGB,
  white: [1.15, 1.15, 1.25] as RGB,
  ember: [1.2, 0.55, 0.18] as RGB,
  grid: [0.10, 0.26, 0.45] as RGB,
  faint: [0.05, 0.12, 0.2] as RGB,
  roseDim: [0.9, 0.16, 0.42] as RGB,
};

export const DURATION = 8;

/* --------------------------------------------------------------- keyframes */

interface Key {
  t: number;
  eye: Vec3;
  target: Vec3;
  ease?: Ease;
}

const CAMERA_KEYS: Key[] = [
  { t: 0.0, eye: [0.0, 0.5, 13.6], target: [0, 0.06, 0] },
  { t: 0.75, eye: [0.0, 0.2, 7.9], target: [0, 0.02, 0], ease: easeOutExpo },
  { t: 1.55, eye: [0.28, 0.08, 6.9], target: [0, 0.02, 0] },
  { t: 2.25, eye: [-0.55, 0.42, 5.9], target: [-0.35, 0.0, -1.2] },
  { t: 3.15, eye: [-1.95, 0.3, 4.6], target: [-0.85, 0.0, -1.4] },
  { t: 3.68, eye: [-0.25, -0.1, 5.5], target: [0.1, 0.0, -1.1], ease: easeInOutExpo },
  { t: 4.2, eye: [0.75, 0.12, 5.7], target: [0.25, 0.0, -1.2] },
  { t: 5.0, eye: [1.85, -0.22, 4.5], target: [0.55, 0.0, -1.3] },
  { t: 5.6, eye: [1.0, 0.5, 6.4], target: [0.3, 0.0, -0.7] },
  { t: 6.08, eye: [0.1, 0.22, 4.2], target: [0, 0.04, 0.62], ease: easeInOutExpo },
  { t: 6.75, eye: [0.0, 0.08, 5.6], target: [0, 0.02, 0.55] },
  { t: 7.4, eye: [0.0, 0.05, 6.6], target: [0, 0, 0] },
  { t: 8.0, eye: [0.0, 0.05, 7.2], target: [0, 0, 0] },
];

/** Time-parameterised Catmull-Rom: C1-continuous, no stop-start at keys. */
function keyedVec(keys: Key[], field: 'eye' | 'target', t: number): Vec3 {
  const n = keys.length;
  if (t <= keys[0].t) return keys[0][field];
  if (t >= keys[n - 1].t) return keys[n - 1][field];
  let i = 0;
  while (i < n - 2 && keys[i + 1].t <= t) i++;
  const k0 = keys[i];
  const k1 = keys[i + 1];
  const h = k1.t - k0.t;
  let u = (t - k0.t) / h;
  if (k1.ease) u = k1.ease(u);

  const pm = keys[Math.max(0, i - 1)];
  const pp = keys[Math.min(n - 1, i + 2)];
  const out: Vec3 = [0, 0, 0];
  for (let c = 0; c < 3; c++) {
    const v0 = k0[field][c];
    const v1 = k1[field][c];
    const m0 = ((v1 - pm[field][c]) / Math.max(1e-4, k1.t - pm.t)) * h;
    const m1 = ((pp[field][c] - v0) / Math.max(1e-4, pp.t - k0.t)) * h;
    const u2 = u * u;
    const u3 = u2 * u;
    const h00 = 2 * u3 - 3 * u2 + 1;
    const h10 = u3 - 2 * u2 + u;
    const h01 = -2 * u3 + 3 * u2;
    const h11 = u3 - u2;
    out[c] = h00 * v0 + h10 * m0 + h01 * v1 + h11 * m1;
  }
  return out;
}

/* ----------------------------------------------------------------- helpers */

/** Glitch windows (seconds) — hard cuts, each one lands on a beat. */
export const GLITCH_WINDOWS: Array<[number, number]> = [
  [1.97, 2.15],
  [3.47, 3.65],
  [5.53, 5.71],
  [5.98, 6.14],
];

/** Cut points — each one lands inside a glitch window, on the beat grid. */
export const CUTS = [2.0, 3.5, 5.56];

export function glitchAmount(t: number): number {
  let g = 0;
  for (const [a, b] of GLITCH_WINDOWS) {
    if (t >= a && t <= b) {
      const u = (t - a) / (b - a);
      g = Math.max(g, Math.sin(u * Math.PI) ** 0.85 * 0.82);
    }
  }
  return g;
}

/** 1 at the exact onset of a detected beat, decaying fast. */
function hitFlash(t: number, decay = 14): number {
  let v = 0;
  for (const b of BEATS) {
    const d = t - b.t;
    if (d >= 0 && d < 1.2) v = Math.max(v, Math.exp(-d * decay) * (0.5 + b.strength * 0.5));
  }
  return v;
}

let BEATS: Analysis['beats'] = [];
let ANA: Analysis | null = null;

/** Per-character entrance driven by a delay, a curve and optional overshoot. */
function charIn(
  t: number,
  start: number,
  opts: {
    dur?: number;
    ease?: Ease;
    from?: [number, number, number];
    scaleFrom?: number;
    rotFrom?: number;
    fade?: number;
    glowDecay?: number;
  } = {},
): CharAnim & { k: number } {
  const dur = opts.dur ?? 0.34;
  const ease = opts.ease ?? easeOutExpo;
  const dt = t - start;
  if (dt <= 0) return { opacity: 0, k: 0 };
  const raw = clamp(dt / dur);
  const k = ease(raw);
  const from = opts.from ?? [0, 0, -7];
  const sf = opts.scaleFrom ?? 1.35;
  const rf = opts.rotFrom ?? 0;
  const fade = opts.fade ?? 0.05;
  return {
    opacity: clamp((dt - fade * 0.2) / Math.max(1e-3, fade)),
    scale: lerp(sf, 1, k),
    offset: [lerp(from[0], 0, k), lerp(from[1], 0, k), lerp(from[2], 0, k)],
    rotZ: lerp(rf, 0, k),
    glow: Math.exp(-Math.max(0, dt - dur * 0.55) * (opts.glowDecay ?? 7)) * (raw < 1.35 ? 1 : 0),
    k: raw,
  };
}

/* -------------------------------------------------------------------- film */

export interface FilmContext {
  w: number;
  h: number;
  analysis: Analysis;
}

export class Film {
  cam = new Camera([0, 0, 13], [0, 0, 0]);
  private sphere = icosphere(1);
  private dust: Vec3[];
  readonly w: number;
  readonly h: number;
  readonly A: Analysis;

  constructor(ctx: FilmContext) {
    this.w = ctx.w;
    this.h = ctx.h;
    this.A = ctx.analysis;
    ANA = ctx.analysis;
    BEATS = ctx.analysis.beats;
    this.cam.resize(ctx.w, ctx.h);
    this.dust = particleField(150, 9, 7);
  }

  /* ------------------------------------------------------------ camera rig */
  private updateCamera(t: number): void {
    const punch = this.A.punch(t, 9);
    const glitch = glitchAmount(t);
    const eye = keyedVec(CAMERA_KEYS, 'eye', t);
    const target = keyedVec(CAMERA_KEYS, 'target', t);

    // hand-held drift + kick shake: high frequencies, tiny amplitudes
    const shake = punch * 0.035 + glitch * 0.12;
    const sx = noise1(t * 26) * shake + noise1(t * 61 + 4) * shake * 0.4;
    const sy = noise1(t * 29 + 11) * shake + noise1(t * 67 + 9) * shake * 0.4;
    const sz = noise1(t * 21 + 23) * shake * 0.5;

    this.cam.eye = [eye[0] + sx, eye[1] + sy, eye[2] + sz];
    this.cam.target = [
      target[0] + sx * 0.6,
      target[1] + sy * 0.6,
      target[2],
    ];
    // subtle bank into the move
    this.cam.roll = Math.sin(t * 1.1) * 0.012 + glitch * 0.06 * noise1(t * 40);
    this.cam.update();
  }

  /* --------------------------------------------------------------- scenes */
  render(t: number): Frame {
    this.updateCamera(t);
    const f = new Frame(this.w, this.h);
    this.background(f, t);

    const energy = this.A.rmsAt(t);
    this.drawDust(f, t, energy);
    this.sceneA(f, t);
    this.sceneB(f, t);
    this.sceneC(f, t);
    this.sceneD(f, t);
    this.sceneE(f, t);
    this.hud(f, t);
    return f;
  }

  /** Ink-black background with a soft cool key light behind the subject. */
  private background(f: Frame, t: number): void {
    const energy = this.A.rmsAt(t);
    f.clear(0.0035, 0.006, 0.014);
    // cool pool of light behind the action
    const cx = f.w * 0.5;
    const cy = f.h * 0.46;
    f.glow(cx, cy, f.h * 0.92, [0.016, 0.038, 0.082], 0.75 + energy * 0.3, 2.6);
    // subtle magenta counter-light from the lower right
    f.glow(f.w * 0.86, f.h * 0.88, f.h * 0.7, [0.05, 0.008, 0.032], 0.4, 2.8);
    // horizon bloom where the perspective grid converges
    const horizon = this.cam.project([0, -1.45, -30]);
    if (horizon.y > 0 && horizon.y < f.h) {
      f.glow(cx, horizon.y, f.w * 0.7, [0.012, 0.03, 0.06], 0.35, 2.4);
    }
  }

  private drawDust(f: Frame, t: number, energy: number): void {
    const pts = this.dust.map((p, i) => {
      const drift = t * 0.12;
      const a = drift + i * 0.013;
      return [
        p[0] * (1 + Math.sin(a) * 0.02),
        p[1] + Math.sin(a * 1.7 + i) * 0.05,
        p[2] + Math.sin(a * 0.6 + i * 2.1) * 0.08,
      ] as Vec3;
    });
    drawParticles(f, this.cam, pts, C.faint.map((x) => x * 1.6) as RGB, {
      size: 1.5,
      opacity: 0.35 + energy * 0.35,
      fog: 1.4,
    });
  }

  /** A — the title slams together out of depth. */
  private sceneA(f: Frame, t: number): void {
    if (t >= 2.0) return;
    const out = clamp((t - 1.9) / 0.1);
    const enter = smoothstep((t - 0.0) / 0.4);
    // power-on: the frame opens as a hairline that blooms into the picture
    if (t < 0.24) {
      const k = clamp(t / 0.2);
      const w = f.w * (0.04 + 0.96 * (1 - Math.pow(1 - k, 3)));
      const open = clamp((t - 0.05) / 0.19);
      const h = f.h * 0.0035 * (1 + 5 * (1 - open));
      const y = f.h * 0.5;
      const life = 1 - clamp((t - 0.1) / 0.14);
      f.line((f.w - w) / 2, y, (f.w + w) / 2, y, C.ice, 1 + 3 * (1 - k), 1.5 * life + 0.25);
      f.line((f.w - w) / 2, y - h, (f.w + w) / 2, y - h, C.cyan, 1, 0.45 * life);
      f.line((f.w - w) / 2, y + h, (f.w + w) / 2, y + h, C.cyan, 1, 0.45 * life);
      f.glow(f.w * 0.5, y, f.w * 0.3 * (0.3 + k), C.ice, 0.4 * life, 2.2);
    }
    const punch = this.A.punch(t, 9);

    // depth ghost: same word, far away, extremely dim — reads as a hologram
    drawText(f, this.cam, {
      text: 'MOTION',
      size: 0.9,
      position: [0, 0.02, -9.5],
      align: 'center',
      tracking: 0.2,
      color: C.cyan,
      weight: 1.6,
      opacity: 0.10 * (1 - out) * enter,
      fog: 1.2,
    });

    const start = 0.16;
    const stepT = 0.115;
    drawText(f, this.cam, {
      text: 'MOTION',
      size: 0.9,
      position: [0, 0.02, 0],
      align: 'center',
      tracking: lerp(0.34, 0.16, easeOutExpo(clamp((t - 0.05) / 1.1))),
      color: mix3(C.white, C.ice, 0.45),
      weight: 1.9,
      opacity: 1 - out,
      fog: 1,
      perChar: (i) => {
        const a = charIn(t, start + i * stepT, {
          dur: 0.34,
          ease: easeOutExpo,
          from: [0, 0, -6.5],
          scaleFrom: 1.5,
          rotFrom: (i % 2 === 0 ? -1 : 1) * 0.18,
        });
        // idle breathing, plus kick-driven scale pulse
        const idle = Math.sin(t * 2.2 + i * 0.7) * 0.012;
        return {
          ...a,
          opacity: (a.opacity ?? 0) * (1 - out),
          scale: (a.scale ?? 1) + idle + punch * 0.03,
          offset: [(a.offset?.[0] ?? 0), (a.offset?.[1] ?? 0), (a.offset?.[2] ?? 0) + punch * 0.06],
          glow: (a.glow ?? 0) + punch * 0.35,
        };
      },
    });

    // a short horizontal impact streak beneath each letter as it lands
    for (let i = 0; i < 6; i++) {
      const st = start + i * stepT;
      const dt = t - st - 0.08;
      if (dt < 0 || dt > 0.5) continue;
      const k = dt / 0.5;
      const x = (i - 2.5) * 0.56;
      const p = this.cam.project([x, -0.26, 0.06]);
      if (!p.ok) continue;
      const halfW = 6 + 34 * easeOutExpo(k);
      const a = (1 - k) ** 1.6;
      f.line(p.x - halfW, p.y, p.x + halfW, p.y, C.ice, 1.6, a * 0.9);
      f.glow(p.x, p.y, halfW * 0.9, C.cyan, a * 0.22, 2.5);
    }

    if (enter > 0) {
      drawGrid(f, this.cam, {
        y: -1.45,
        extent: 13,
        step: 0.65,
        color: C.grid,
        opacity: 0.9 * enter * (1 - out),
        fadeRadius: 11,
      });
    }

    // sub-caption that types itself in, tracking the beat grid
    const capStart = 1.15;
    if (t > capStart) {
      const k = clamp((t - capStart) / 0.5);
      drawText(f, this.cam, {
        text: 'CINEMATIC / CODE DRIVEN',
        size: 0.115,
        position: [0, -0.72, 0.02],
        align: 'center',
        tracking: 0.42,
        color: C.cyan,
        weight: 1.1,
        opacity: easeOutExpo(k) * (1 - out) * 0.95,
      });
    }
  }

  /** B — the camera orbits; the sphere morphs to a torus then a cube. */
  private sceneB(f: Frame, t: number): void {
    if (t < 2.0 || t >= 3.5) return;
    const inK = clamp((t - 2.0) / 0.2);
    const outK = clamp((t - 3.4) / 0.1);
    const op = easeOutExpo(inK) * (1 - easeInOutCubic(outK));
    if (op <= 0.004) return;

    const beatPhase = (((t - (BEATS[0]?.t ?? 0)) % this.A.beat) + this.A.beat) % this.A.beat / this.A.beat;
    const morphT = smoothstep(clamp((t - 2.05) / 1.1));
    const shapeB: ShapeName = morphT < 0.5 ? 'torus' : 'cube';
    const m = morph(this.sphere, 'sphere', shapeB, morphT < 0.5 ? morphT * 2 : (morphT - 0.5) * 2, 1.0);

    const objPos: Vec3 = [1.72, 0.05, -2.55];
    drawMesh(f, this.cam, m, C.blue, {
      position: objPos,
      rotation: [0.55 + t * 0.32, t * 0.62, 0.18],
      opacity: 0.5 * op,
      weight: 1.05,
      fog: 1.25,
      scale: 1 + Math.sin(beatPhase * Math.PI) * 0.035,
    });

    // orbit rings: three thin arcs in different planes, spinning at different rates
    for (let r = 0; r < 3; r++) {
      const radius = 1.28 + r * 0.17;
      const pts: Vec3[] = [];
      const N = 64;
      const spin = t * (0.45 + r * 0.22) * (r % 2 ? -1 : 1);
      for (let i = 0; i < N; i++) {
        const a = (i / N) * Math.PI * 2;
        let p: Vec3 = [Math.cos(a) * radius, Math.sin(a) * radius, 0];
        // tilt each ring differently
        const tilt = 0.9 + r * 0.85;
        p = [p[0], p[1] * Math.cos(tilt), p[1] * Math.sin(tilt)];
        // yaw the whole ring
        const c = Math.cos(spin), sn = Math.sin(spin);
        p = [p[0] * c + p[2] * sn, p[1], -p[0] * sn + p[2] * c];
        pts.push([p[0] + objPos[0], p[1] + objPos[1], p[2] + objPos[2]]);
      }
      for (let i = 0; i < N; i++) {
        const p = this.cam.project(pts[i]);
        const q = this.cam.project(pts[(i + 1) % N]);
        if (!p.ok || !q.ok) continue;
        // only draw the front half so it reads as an orbit, not a cage
        const facing = p.depth;
        const a = op * 0.38 * (0.45 + 0.55 * (1 - clamp(facing / 9)));
        f.line(p.x, p.y, q.x, q.y, r === 1 ? C.magenta : C.cyan, 1, a);
      }
    }

    const tx = -1.05;
    drawText(f, this.cam, {
      text: 'BY CODE',
      size: 0.5,
      position: [tx, 0.2, -1.05],
      rotation: [0, 0.34, 0],
      align: 'center',
      tracking: lerp(0.8, 0.15, easeOutBack(1.4)(clamp((t - 1.95) / 0.8))),
      color: mix3(C.white, C.ice, 0.45),
      weight: 1.9,
      opacity: op,
      perChar: (i) => {
        const a = charIn(t, 1.95 + i * 0.045, { dur: 0.42, from: [0, 0, -4.5], scaleFrom: 1.3 });
        return { ...a, opacity: (a.opacity ?? 0) * op, glow: (a.glow ?? 0) + this.A.punch(t) * 0.22 };
      },
    });

    drawText(f, this.cam, {
      text: 'NO KEYFRAME WAS CLICKED',
      size: 0.082,
      position: [tx - 0.02, -0.4, -1.02],
      rotation: [0, 0.34, 0],
      align: 'center',
      tracking: 0.32,
      color: C.roseDim,
      weight: 1.05,
      opacity: easeOutExpo(clamp((t - 2.5) / 0.4)) * op * 0.9,
    });

    // vertical rule that draws itself next to the type block
    const draw = easeOutExpo(clamp((t - 2.15) / 0.6));
    if (draw > 0) {
      const a = this.cam.project([tx - 0.86, 0.44, -1.05]);
      const b = this.cam.project([tx - 0.86, 0.44 - 1.05 * draw, -1.05]);
      if (a.ok && b.ok) f.line(a.x, a.y, b.x, b.y, C.cyan, 1.2, op * 0.5);
    }
  }

  /** C — stacked kinetic lines, HUD ticks, a knot of light. */
  private sceneC(f: Frame, t: number): void {
    if (t < 3.5 || t >= 5.56) return;
    const out = clamp((t - 5.46) / 0.1);
    const inK = clamp((t - 3.5) / 0.15);
    const op = easeOutExpo(inK) * (1 - easeInOutCubic(out));
    if (op <= 0.004) return;
    const punch = this.A.punch(t, 10);

    const base: Vec3 = [-1.72, 0, -1.0];
    const rot: Vec3 = [0, 0.36, 0];
    const lines = ['PIXELS', 'OVER', 'TIME'];
    const sizes = [0.4, 0.26, 0.4];
    const colors = [C.white, C.magenta, C.ice];

    lines.forEach((text, li) => {
      const lineStart = 3.52 + li * 0.24;
      const y = 0.5 - li * 0.46;
      const se = easeOutExpo(clamp((t - lineStart) / 0.45));
      drawText(f, this.cam, {
        text,
        size: sizes[li],
        position: [base[0] + (1 - se) * 1.1, base[1] + y, base[2]],
        rotation: rot,
        align: 'left',
        tracking: 0.2,
        color: colors[li],
        weight: 1.8,
        opacity: op * clamp((t - lineStart) / 0.08),
        perChar: (i) => {
          const st = lineStart + i * 0.038;
          const dt = t - st;
          const k = easeOutExpo(clamp(dt / 0.42));
          return {
            opacity: clamp(dt / 0.07),
            scale: lerp(1.22, 1, k),
            offset: [lerp(0.55, 0, k), 0, lerp(-3.4, 0, k)],
            rotZ: lerp(0.1, 0, k) * (li === 1 ? -1 : 1),
            glow: Math.exp(-Math.max(0, dt) * 6) * 0.75 + punch * 0.28,
          };
        },
      });
    });

    // the knot: a thin wireframe object orbiting to the right of the type
    const m = morph(this.sphere, 'knot', 'knot', 0, 0.52);
    drawMesh(f, this.cam, m, C.magenta, {
      position: [0.95, 0.02, -0.55],
      rotation: [0.9 + t * 0.22, t * 1.15, t * 0.28],
      opacity: 0.48 * op,
      weight: 0.95,
      fog: 1.05,
    });

    // a big ghost numeral far behind, providing parallax depth
    drawText(f, this.cam, {
      text: '03',
      size: 4.0,
      position: [2.15, -0.55, -15.0],
      align: 'center',
      tracking: 0.05,
      color: C.blue,
      weight: 1.2,
      opacity: op * 0.07,
      fog: 1.6,
    });

    // HUD ticks riding the beat, along the bottom of the composition
    const cols = 16;
    const beatTick = Math.floor((t * 8) % cols);
    for (let i = 0; i < cols; i++) {
      const x = -1.15 + i * 0.155;
      const p = this.cam.project([x, -0.86, -0.95]);
      const h = 0.05 + (i === beatTick ? 0.16 : ((i * 7) % 5) * 0.018);
      const q = this.cam.project([x, -0.86 - h, -0.95]);
      if (!p.ok || !q.ok) continue;
      f.line(p.x, p.y, q.x, q.y, i === beatTick ? C.ice : C.cyan, 1.1, op * (i === beatTick ? 0.9 : 0.45));
    }

    // a prompt being typed — the film's own origin story
    const prompt = 'CREATE A 15 SECOND CINEMATIC ANIMATION';
    const typeStart = 4.02;
    const typed = Math.max(0, Math.min(prompt.length, Math.floor((t - typeStart) * 34)));
    if (typed > 0) {
      const p0: Vec3 = [-0.05, -0.72, -1.0];
      drawText(f, this.cam, {
        text: prompt.slice(0, typed),
        size: 0.058,
        position: p0,
        rotation: [0, 0.36, 0],
        align: 'left',
        tracking: 0.2,
        color: C.white,
        weight: 1,
        opacity: op * 0.72,
      });
      // caret
      const caretOn = Math.floor(t * 4) % 2 === 0;
      if (caretOn && typed < prompt.length) {
        const { width } = layoutCache(prompt.slice(0, typed), 0.2);
        const a = this.cam.project([p0[0] + width * 0.058 + 0.03, -0.7, -1.0]);
        const b = this.cam.project([p0[0] + width * 0.058 + 0.03, -0.75, -1.0]);
        if (a.ok && b.ok) f.line(a.x, a.y, b.x, b.y, C.ice, 1.4, op * 0.9);
      }
    }

    // a thin frame line drawing around the type block
    const frameK = easeOutExpo(clamp((t - 3.9) / 0.7));
    if (frameK > 0) {
      const x0 = -1.78, y0 = 0.72, x1 = -1.78 + 2.12 * frameK, y1 = -0.42;
      const a = this.cam.project([x0, y0, -1.0]);
      const b = this.cam.project([x1, y1, -1.0]);
      if (a.ok && b.ok) {
        f.line(a.x, a.y, b.x, a.y, C.cyan, 1, op * 0.35);
        f.line(b.x, a.y, b.x, b.y, C.cyan, 1, op * 0.35);
        f.line(b.x, b.y, a.x, b.y, C.cyan, 1, op * 0.35);
      }
    }
  }

  /** D — the drop: the wordmark hits the lens and the mesh shatters. */
  private sceneD(f: Frame, t: number): void {
    if (t < 5.56 || t >= 7.12) return;
    const inK = clamp((t - 5.56) / 0.18);
    const out = clamp((t - 7.02) / 0.1);
    const op = easeOutExpo(inK) * (1 - easeInOutCubic(out));
    if (op <= 0.004) return;
    const punch = this.A.punch(t, 8);
    const drop = 5.99;

    // shatter intensity spikes on the drop and on every kick
    const shatter = 0.05 + punch * 0.5 + Math.max(0, 0.9 - (t - drop) * 2.2) * 0.6;
    const m = morph(this.sphere, 'cube', 'octa', smoothstep(clamp((t - 6.1) / 1.2)), 1.1);
    drawMesh(f, this.cam, m, C.blue, {
      position: [0.0, 0.02, -3.1],
      rotation: [t * 0.6, t * 0.9, t * 0.2],
      opacity: 0.5 * op,
      weight: 1.1,
      fog: 1.0,
      scale: 2.15,
      shatter: shatter * 0.9,
      seed: Math.floor(t * 30),
    });

    drawText(f, this.cam, {
      text: 'MOTION',
      size: 0.72,
      position: [0, 0.16, 0.62],
      align: 'center',
      tracking: 0.15,
      color: mix3(C.white, C.ice, 0.35),
      weight: 2.1,
      opacity: op,
      perChar: (i) => {
        const dt = t - (5.66 + i * 0.05);
        const k = clamp(dt / 0.55);
        const sl = easeOutElastic(clamp(dt / 0.7));
        return {
          opacity: clamp(dt / 0.06) * (1 - out),
          scale: lerp(2.6, 1, sl) + punch * 0.04,
          offset: [0, 0, (1 - easeOutBack(2.2)(k)) * 2.2 + punch * 0.1],
          rotZ: (1 - k) * (i % 2 ? 0.1 : -0.1),
          glow: punch * 0.45 + (1 - k) * 0.35,
        };
      },
    });

    drawText(f, this.cam, {
      text: 'BY CODE',
      size: 0.155,
      position: [0, -0.42, 0.62],
      align: 'center',
      tracking: lerp(1.1, 0.55, easeOutExpo(clamp((t - 6.35) / 0.6))),
      color: C.magenta,
      weight: 1.4,
      opacity: clamp((t - 6.35) / 0.25) * op,
    });

    // scanner beam that sweeps through the lockup on the drop
    const sweep = clamp((t - 5.99) / 0.42);
    if (sweep > 0 && sweep < 1) {
      const x = lerp(-2.55, 2.55, easeOutExpo(sweep));
      const a = this.cam.project([x, 0.42, 0.6]);
      const b = this.cam.project([x, -0.72, 0.6]);
      if (a.ok && b.ok) {
        const fade = Math.sin(sweep * Math.PI) ** 0.5;
        f.line(a.x, a.y, b.x, b.y, C.white, 2.6, fade * 0.95);
        for (let i = 0; i < 5; i++) {
          const yy = a.y + ((b.y - a.y) * (i + 0.5)) / 5;
          f.glow(a.x, yy, 46, C.ice, fade * 0.12, 2.4);
        }
      }
    }
  }

  /** E — end card: the mark resolves out of the wireframe. */
  private sceneE(f: Frame, t: number): void {
    if (t < 7.08) return;
    const k = clamp((t - 7.08) / 0.5);
    const e = easeOutExpo(k);
    const out = clamp((t - 7.86) / 0.14);
    const op = e * (1 - out);
    if (op <= 0.004) return;

    // outer ring drawing itself on
    const pts = ring(64, 2.0, 0.95);
    for (let i = 0; i < pts.length; i++) {
      const seg = i / pts.length;
      if (seg > e * 1.05) break;
      const p = this.cam.project(pts[i]);
      const q = this.cam.project(pts[(i + 1) % pts.length]);
      if (!p.ok || !q.ok) continue;
      f.line(p.x, p.y, q.x, q.y, C.cyan, 1.4, op * 0.55);
    }
    // inner ring, counter-rotating slowly
    const inner = ring(44, 1.52, 0.95).map(([x, y, z]) => [x * Math.cos(t * 0.8), y, z] as Vec3);
    for (let i = 0; i < inner.length; i++) {
      const p = this.cam.project(inner[i]);
      const q = this.cam.project(inner[(i + 1) % inner.length]);
      if (!p.ok || !q.ok) continue;
      f.line(p.x, p.y, q.x, q.y, C.magenta, 1, op * 0.26);
    }

    const c0 = this.cam.project([0, 0, 0]);
    f.glow(c0.x, c0.y, this.h * 0.22, [0.03, 0.07, 0.14], op * 0.9, 2.2);

    drawText(f, this.cam, {
      text: 'MOTION',
      size: 0.42,
      position: [0, 0.16, 0],
      align: 'center',
      tracking: lerp(0.7, 0.3, e),
      color: C.white,
      weight: 1.5,
      opacity: op,
      perChar: (i) => ({ glow: 0.3 + Math.sin(t * 3 + i) * 0.1 }),
    });
    drawText(f, this.cam, {
      text: 'BY CODE',
      size: 0.16,
      position: [0, -0.27, 0],
      align: 'center',
      tracking: lerp(1.2, 0.72, e),
      color: C.ice,
      weight: 1.1,
      opacity: op * 0.95,
    });
    drawText(f, this.cam, {
      text: 'ANS MALIK / 2026',
      size: 0.085,
      position: [0, -0.92, 0],
      align: 'center',
      tracking: 0.36,
      color: C.cyan,
      weight: 1,
      opacity: op * 0.6,
    });
  }

  /** Persistent, very light framing marks — the "monitor" feel. */
  private hud(f: Frame, t: number): void {
    const m = 34;
    const len = 26;
    const op = 0.28 * smoothstep(clamp(t / 0.6)) * (1 - clamp((t - 7.9) / 0.1));
    const col = C.cyan;
    const corners: Array<[number, number, number, number]> = [
      [m, m, 1, 1],
      [this.w - m, m, -1, 1],
      [m, this.h - m, 1, -1],
      [this.w - m, this.h - m, -1, -1],
    ];
    for (const [x, y, sx, sy] of corners) {
      f.line(x, y, x + len * sx, y, col, 1, op);
      f.line(x, y, x, y + len * sy, col, 1, op);
    }
    // bottom-left running timecode
    const frameNo = Math.round(t * 30);
    const s = `${String(Math.floor(frameNo / 30)).padStart(2, '0')}:${String(frameNo % 30).padStart(2, '0')}`;
    const p = this.cam.project([0, 0, 0]);
    drawTextHud(f, s, m + 8, this.h - m - 26, 0.7 * op);
    // top-right label
    drawTextHud(f, 'MOTION / BY CODE', this.w - m - 150, m + 10, 0.5 * op);
    void p;
  }
}

/** Screen-space UI text (not part of the 3D world). */
function drawTextHud(f: Frame, text: string, x: number, y: number, op: number): void {
  const size = 9;
  let px = x;
  for (const ch of text) {
    const g = ch === ' ' ? null : glyph(ch);
    if (g) {
      for (const stroke of g.strokes) {
        for (let i = 1; i < stroke.length; i++) {
          f.line(
            px + stroke[i - 1][0] * size,
            y + (1 - stroke[i - 1][1]) * size,
            px + stroke[i][0] * size,
            y + (1 - stroke[i][1]) * size,
            C.cyan,
            1,
            op,
          );
        }
      }
    }
    px += (g ? g.w : 0.34) * size + 2;
  }
}

import { glyphFor as glyph, layout as layoutCache } from './graphics/font.ts';

/* --------------------------------------------------------------- finishing */

export interface PostOptions {
  bloom?: number;
  aberration?: number;
  letterbox?: number;
  grain?: number;
  vignette?: number;
}

export function postProcess(f: Frame, t: number, glitchAmt: number, o: PostOptions = {}): Frame {
  let out = f;
  const gl = glitchAmt;
  if (gl > 0.001) out = FX.glitch(out, { amount: gl, t });
  out = FX.lensDistort(out, -0.03);
  out = FX.chromaticAberration(out, (o.aberration ?? 0.7) + gl * 6);
  out = FX.bloom(out, { threshold: 0.34, radius: 4, intensity: o.bloom ?? 0.8, wide: 0.42 });
  FX.streak(out, 0.9 + gl * 1.4);
  FX.scanlines(out, t, 3, 0.07);
  FX.vignette(out, 0.7, 2.1);
  FX.grain(out, t, o.grain ?? 0.005);
  if (o.letterbox) {
    const bar = Math.round(out.h * o.letterbox);
    for (let y = 0; y < out.h; y++) {
      if (y >= bar && y < out.h - bar) continue;
      for (let x = 0; x < out.w; x++) {
        const i = (y * out.w + x) * 3;
        out.data[i] = 0;
        out.data[i + 1] = 0;
        out.data[i + 2] = 0;
      }
    }
  }
  return out;
}
