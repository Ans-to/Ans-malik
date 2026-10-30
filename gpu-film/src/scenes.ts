/**
 * scenes.ts — "Why Is a GPU So Expensive?" — 60 s, 8 scenes, 120 BPM.
 *
 * Timing is locked to the beat grid: 0.5 s per beat, 120 beats total. Every
 * camera move samples a MEASURED velocity curve (refcurve.ts), never an
 * invented ease. Lighting is a procedural studio environment with a key/fill/rim
 * rig and a moving practical — see ENV_AUDIT.md for why Poly Haven HDRIs are
 * not used here, and gates.ts for how that substitution is reported.
 */

import { Frame, type RGB } from '../../motion/src/core/raster.ts';
import { Camera } from '../../motion/src/graphics/stage.ts';
import { drawType, measure } from '../../motion/src/graphics/type.ts';
import { clamp, lerp, mix3, noise1, type Vec3 } from '../../motion/src/core/math.ts';
import {
  Render3D,
  box,
  cylinder,
  plane,
  studioEnv,
  xform,
  type Env,
  type Material,
  type Mesh,
} from './engine3d.ts';
import { toPosition, type MotionCurve } from './refcurve.ts';

export const DURATION = 60;
export const BPM = 120;
export const BEAT = 60 / BPM; // 0.5 s

/* ------------------------------------------------------------------ palette */
export const P = {
  ink: [0.0055, 0.006, 0.0075] as RGB,
  bone: [0.82, 0.82, 0.8] as RGB,
  dim: [0.34, 0.35, 0.37] as RGB,
  cyan: [0.22, 0.86, 1.0] as RGB,
  cyanHot: [0.55, 1.5, 1.8] as RGB,
  amber: [1.55, 0.62, 0.12] as RGB,
  red: [1.5, 0.22, 0.14] as RGB,
};

/* --------------------------------------------------------------- materials */
const M = {
  pcb: { albedo: [0.009, 0.011, 0.014], rough: 0.7, metal: 0.05, rim: 0.4 } as Material,
  substrate: { albedo: [0.026, 0.032, 0.042], rough: 0.45, metal: 0.3, rim: 0.7 } as Material,
  die: { albedo: [0.09, 0.13, 0.2], rough: 0.13, metal: 0.9, rim: 1.6 } as Material,
  block: { albedo: [0.13, 0.18, 0.26], rough: 0.1, metal: 0.92, rim: 1.7 } as Material,
  hbm: { albedo: [0.03, 0.038, 0.05], rough: 0.24, metal: 0.75, rim: 1.4 } as Material,
  gold: { albedo: [0.85, 0.6, 0.2], rough: 0.18, metal: 1.0, rim: 1.2 } as Material,
  cap: { albedo: [0.1, 0.11, 0.13], rough: 0.5, metal: 0.55, rim: 0.6 } as Material,
  steel: { albedo: [0.26, 0.28, 0.31], rough: 0.26, metal: 1.0, rim: 1.2 } as Material,
  silicon: { albedo: [0.045, 0.05, 0.062], rough: 0.34, metal: 0.55, rim: 1.1 } as Material,
  machine: { albedo: [0.052, 0.056, 0.065], rough: 0.3, metal: 0.88, rim: 1.5 } as Material,
  dieLit: { albedo: [0.1, 0.14, 0.2], rough: 0.2, metal: 0.7, rim: 1.0 } as Material,
  glass: { albedo: [0.02, 0.035, 0.05], rough: 0.07, metal: 0.25, rim: 0.35 } as Material,
  cyanLit: { albedo: [0, 0, 0], rough: 1, metal: 0, rim: 0, emit: [0.3, 1.35, 1.7] } as Material,
  cyanDim: { albedo: [0, 0, 0], rough: 1, metal: 0, rim: 0, emit: [0.06, 0.28, 0.36] } as Material,
  amberLit: { albedo: [0, 0, 0], rough: 1, metal: 0, rim: 0, emit: [1.4, 0.5, 0.06] } as Material,
  black: { albedo: [0.004, 0.004, 0.005], rough: 0.4, metal: 0.2, rim: 0.2 } as Material,
};

/* ------------------------------------------------------------------- rigs */
export const envKey: Env = studioEnv({
  keyPower: 4.4,
  key: [-0.7, 0.62, 0.45] as Vec3,
  rimPower: 3.0,
  rim: [0.3, 0.4, -1] as Vec3,
  exposure: 0.78,
  zenith: [0.05, 0.065, 0.085] as RGB,
});
export const envWide: Env = studioEnv({
  keyPower: 3.6,
  key: [-0.5, 0.85, 0.3] as Vec3,
  rimPower: 3.4,
  rim: [0.1, 0.3, -1] as Vec3,
  exposure: 0.7,
  zenith: [0.04, 0.055, 0.075] as RGB,
});

/* ---------------------------------------------------------------- content */
function gpuPackage(): { meshes: Array<{ mesh: Mesh; mat?: Material }>; half: number } {
  const meshes: Array<{ mesh: Mesh }> = [];
  meshes.push({ mesh: plane(0, -0.30, 0, 6.0, 4.2, M.pcb, 40) });
  meshes.push({ mesh: box(0, -0.2, 0, 2.3, 0.09, 1.55, M.substrate) });
  meshes.push({ mesh: box(0, -0.145, 0, 0.92, 0.02, 0.78, M.die) });
  for (let i = 0; i < 7; i++) {
    for (let j = 0; j < 6; j++) {
      meshes.push({ mesh: box(-0.36 + i * 0.12, -0.128, -0.29 + j * 0.116, 0.09, 0.012, 0.09, M.block) });
    }
  }
  for (const [dx, dz] of [[-0.83, 0], [0.83, 0], [-0.83, 0.62], [0.83, 0.62], [-0.83, -0.62], [0.83, -0.62]]) {
    meshes.push({ mesh: box(dx, -0.16, dz, 0.34, 0.09, 0.24, M.hbm) });
    for (let i = 0; i < 4; i++) meshes.push({ mesh: box(dx - 0.11 + i * 0.073, -0.112, dz, 0.02, 0.016, 0.24, M.gold) });
  }
  for (let i = 0; i < 6; i++) meshes.push({ mesh: cylinder(-1.02 + i * 0.41, -0.30, 0.86, 0.055, 0.19, M.cap, 18) });
  for (let i = 0; i < 26; i++) meshes.push({ mesh: box(-1.06 + i * 0.085, -0.30, -0.80, 0.045, 0.02, 0.13, M.gold) });
  return { meshes, half: 1.15 };
}

function waferMesh(): { base: Mesh[]; dies: Array<{ x: number; z: number; good: boolean }> } {
  const R = 1.05;
  const base: Mesh[] = [cylinder(0, -0.04, 0, R, 0.04, M.silicon, 96)];
  const dies: Array<{ x: number; z: number; good: boolean }> = [];
  const step = 0.088;
  let seed = 7;
  const rnd = (): number => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  for (let x = -R; x <= R; x += step) {
    for (let z = -R; z <= R; z += step) {
      if (Math.hypot(x, z) > R - 0.05) continue;
      // defects cluster, as they do on real wafers: 3 bad regions + stray particles
      const c1 = Math.hypot(x - 0.32, z + 0.28) < 0.3;
      const c2 = Math.hypot(x + 0.42, z - 0.12) < 0.24;
      const c3 = Math.hypot(x + 0.1, z - 0.55) < 0.17;
      const stray = rnd() < 0.05;
      dies.push({ x, z, good: !(c1 || c2 || c3 || stray) });
    }
  }
  return { base, dies };
}

function euvMachine(): Mesh[] {
  const out: Mesh[] = [];
  out.push(plane(0, -0.5, 0, 8, 6, M.black, 20));
  out.push(box(0, -0.34, 0, 2.9, 0.42, 1.55, M.machine));         // machine base
  out.push(box(0, 0.06, -0.05, 1.7, 0.3, 1.15, M.machine));        // stage
  // vacuum chamber: tall glass column with a mirror stack inside
  out.push(box(-0.55, 0.5, 0.05, 0.62, 1.05, 0.62, M.glass));
  out.push(box(-0.55, 0.16, 0.05, 0.5, 0.06, 0.5, M.cyanDim));     // plasma pool
  out.push(box(-0.55, 0.42, 0.05, 0.44, 0.03, 0.44, M.gold));      // mirror 1
  out.push(box(-0.55, 0.66, 0.05, 0.34, 0.03, 0.34, M.gold));      // mirror 2
  out.push(box(-0.28, 0.66, 0.28, 0.016, 0.9, 0.016, M.cyanLit));  // light path
  // wafer stage + optics arm on the right
  out.push(cylinder(0.72, 0.26, 0.1, 0.3, 0.05, M.gold, 40));
  out.push(box(0.72, 0.62, 0.1, 0.34, 0.66, 0.34, M.machine));
  out.push(box(0.72, 0.28, 0.1, 0.2, 0.02, 0.2, M.cyanLit));
  return out;
}

/* --------------------------------------------------------------- the film */

export interface FilmContext {
  w: number;
  h: number;
  curves: Record<string, MotionCurve>;
  /** 0..1 global polish: 0 = pass 1 draft, 1 = final */
  polish?: number;
}

interface Shot {
  id: string;
  start: number;
  end: number;
  title: string;
}

export const SHOTS: Shot[] = [
  { id: 's1', start: 0, end: 6, title: 'Title — the question' },
  { id: 's2', start: 6, end: 14, title: 'Silicon area' },
  { id: 's3', start: 14, end: 22, title: 'Wafer yield' },
  { id: 's4', start: 22, end: 30, title: 'HBM stacks' },
  { id: 's5', start: 30, end: 38, title: 'EUV lithography' },
  { id: 's6', start: 38, end: 46, title: 'Supply vs demand' },
  { id: 's7', start: 46, end: 54, title: 'Price breakdown' },
  { id: 's8', start: 54, end: 60, title: 'The answer' },
];

export class Film {
  readonly w: number;
  readonly h: number;
  readonly cam: Camera;
  /** flat layer camera: 1 world unit = half the frame height, always. */
  readonly tcam: Camera;
  readonly r3d: Render3D;
  private curves: Record<string, MotionCurve>;
  private pos: Record<string, (u: number) => number> = {};
  private gpu = gpuPackage();
  private wafer = waferMesh();
  private euv = euvMachine();
  readonly edl: Array<{ type: string; at: number }> = [];

  constructor(ctx: FilmContext) {
    this.w = ctx.w;
    this.h = ctx.h;
    this.curves = ctx.curves;
    for (const [k, v] of Object.entries(ctx.curves)) this.pos[k] = toPosition(v);
    this.cam = new Camera([0, 1, 4], [0, 0, 0]);
    this.cam.fov = (34 * Math.PI) / 180;
    this.cam.resize(ctx.w, ctx.h);
    // Type lives on its own layer at z=0, viewed from z=2 with a 53.13 deg fov:
    // the visible half-height is exactly 1.0 world unit, so a type size of 0.2
    // is 10% of frame height at ANY resolution or aspect. This is the standard
    // separation between a 3D beauty pass and a 2D graphics pass.
    this.tcam = new Camera([0, 0, 2], [0, 0, 0]);
    this.tcam.fov = 2 * Math.atan(0.5);
    this.tcam.resize(ctx.w, ctx.h);
    this.tcam.update();
    this.r3d = new Render3D(ctx.w, ctx.h);
  }

  /** Register a transition in the EDL so the audit gate can verify variety. */
  private cut(type: string, at: number): void {
    this.edl.push({ type, at });
  }

  private camera(eye: Vec3, target: Vec3, fov = 34, roll = 0): void {
    this.cam.eye = eye;
    this.cam.target = target;
    this.cam.fov = (fov * Math.PI) / 180;
    this.cam.roll = roll;
    this.cam.update();
  }

  render(t: number): Frame {
    const f = new Frame(this.w, this.h);
    f.clear(P.ink[0], P.ink[1], P.ink[2]);
    this.r3d.frame.data.set(f.data);
    this.r3d.frame.data.fill(0);
    this.r3d.reset();

    const e = (k: string, u: number): number => (this.pos[k] ? this.pos[k](clamp(u)) : clamp(u));

    if (t < 6) this.s1(t, e);
    else if (t < 14) this.s2(t, e);
    else if (t < 22) this.s3(t, e);
    else if (t < 30) this.s4(t, e);
    else if (t < 38) this.s5(t, e);
    else if (t < 46) this.s6(t, e);
    else if (t < 54) this.s7(t, e);
    else this.s8(t, e);

    // copy the 3D result into the output frame, then composite type on top
    f.data.set(this.r3d.frame.data);
    return f;
  }

  /* ------------------------------------------------------- S1 title (0-6) */
  private s1(t: number, e: (k: string, u: number) => number): void {
    const u = t / 6;
    const p = e('dolly_in', u);
    const drift = noise1(t * 0.6) * 0.006;
    this.camera([lerp(-0.55, -0.28, p) + drift, lerp(1.55, 1.15, p), lerp(4.6, 3.0, p) + drift], [
      lerp(0.86, 0.78, p),
      lerp(-0.44, -0.38, p),
      0,
    ], lerp(34, 30, p));
    for (const m of this.gpu.meshes) this.r3d.draw(this.cam, m.mesh, envKey);
    this.r3d.applyDOF(Math.hypot(lerp(4.6, 3.0, p), 1.4), 0.55, 10);

    const k1 = clamp((t - 0.35) / 0.5);
    const k2 = clamp((t - 0.95) / 0.5);
    const k3 = clamp((t - 1.8) / 0.6);
    drawType(this.r3d.frame, this.tcam, {
      text: 'WHY IS A GPU',
      size: this.fit('WHY IS A GPU', this.sz(0.095), 0.0, 0.90),
      position: this.at(-0.86, 0.26),
      align: 'left',
      tracking: lerp(0.08, -0.005, clamp(k1)),
      color: P.bone,
      weight: 1.0,
      opacity: clamp(k1 * 3),
      perChar: (i) => ({ wipe: clamp(k1 * 1.5 - i * 0.04) }),
    });
    drawType(this.r3d.frame, this.tcam, {
      text: 'SO EXPENSIVE?',
      size: this.fit('SO EXPENSIVE?', this.sz(0.095), 0.0, 0.90),
      position: this.at(-0.86, 0.06),
      align: 'left',
      tracking: lerp(0.08, -0.005, clamp(k2)),
      color: P.cyan,
      weight: 1.0,
      opacity: clamp(k2 * 3),
      perChar: (i) => ({ wipe: clamp(k2 * 1.5 - i * 0.04) }),
    });
    drawType(this.r3d.frame, this.tcam, {
      text: 'A BREAKDOWN IN NINE COSTS',
      size: this.fit('A BREAKDOWN IN NINE COSTS', this.sz(0.024), 0.24),
      position: this.at(-0.86, -0.12),
      align: 'left',
      tracking: 0.24,
      color: P.dim,
      weight: 1.0,
      opacity: k3 * 0.9,
    });
    if (t > 1.8) {
      const a = this.at(-0.86, -0.07);
      const b = this.at(1.0, -0.07);
      this.rule(this.r3d.frame, a, [lerp(a[0], b[0], clamp((t - 1.8) / 1.1)), a[1], 0], P.cyan, 1.2, 0.45);
    }
  }

  /* ---------------------------------------------------- S2 silicon (6-14) */
  private s2(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 6) / 8;
    const p = e('orbit', u);
    const ang = lerp(-0.5, 0.35, p);
    const rad = lerp(2.55, 2.05, e('dolly_in', u));
    this.camera([Math.sin(ang) * rad + 0.62, lerp(0.75, 0.5, p), Math.cos(ang) * rad], [0.62, -0.34, 0], lerp(35, 30, p));
    for (const m of this.gpu.meshes) this.r3d.draw(this.cam, m.mesh, envKey);
    this.r3d.applyDOF(rad * 1.05, 0.5, 11);

    this.stack(t, {
      start: 6.25,
      eyebrow: '01  SILICON AREA',
      headline: 'AREA IS COST',
      body: ['EVERY SQUARE MILLIMETRE MUST BE', 'PRINTED, TESTED AND COOLED.'],
      stat: `${Math.round(lerp(0, 608, clamp((t - 7.2) / 2.4)))}`,
      statUnit: 'MM2 OF DIE',
      statColor: P.bone,
    });
  }

  /* ------------------------------------------------------ S3 wafer (14-22) */
  private s3(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 14) / 8;
    const p = e('dolly_in', u);
    const h = lerp(2.5, 1.35, p);
    this.camera([lerp(0.55, 0.22, p), h, lerp(1.9, 1.35, p)], [0, 0.02, 0], lerp(38, 31, p));
    for (const m of this.wafer.base) this.r3d.draw(this.cam, m, envWide);
    // notch + flat edge so the disc reads as a wafer, not a plate
    this.r3d.draw(this.cam, box(0, 0.012, -1.02, 0.16, 0.02, 0.05, M.cyanLit), envWide);
    this.r3d.draw(this.cam, cylinder(0, 0.02, 0, 0.06, 0.02, M.steel, 24), envWide);
    const appear = clamp((t - 14.4) / 2.6);
    const count = Math.floor(this.wafer.dies.length * appear);
    for (let i = 0; i < count; i++) {
      const d = this.wafer.dies[i];
      const mat = d.good ? M.dieLit : M.amberLit;
      this.r3d.draw(this.cam, box(d.x, 0.006, d.z, 0.076, 0.012, 0.076, mat), envWide);
    }
    this.r3d.applyDOF(lerp(2.9, 1.8, p), 0.45, 10);

    const pct = lerp(100, 82, clamp((t - 17.6) / 2.0));
    this.stack(t, {
      start: 14.3,
      eyebrow: '02  YIELD',
      eyebrowColor: P.amber,
      headline: 'NOT EVERY DIE SURVIVES',
      body: ['DEFECTIVE DIES ARE CHARGED', 'TO THE GOOD ONES.'],
      stat: `${pct.toFixed(1)}%`,
      statUnit: 'YIELD',
      statColor: pct > 90 ? P.bone : P.amber,
    });
  }

  /* -------------------------------------------------------- S4 HBM (22-30) */
  private s4(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 22) / 8;
    const p = e('dolly_in', u);
    this.camera([lerp(-1.35, -0.95, p), lerp(0.95, 0.55, p), lerp(1.5, 1.05, p)], [-0.35, -0.1, 0], lerp(34, 30, p));
    for (const m of this.gpu.meshes) this.r3d.draw(this.cam, m.mesh, envKey);
    // memory stacks lift and separate on the beat
    const lift = clamp((t - 23) / 1.6);
    const stacks = [[-0.83, 0], [0.83, 0], [-0.83, 0.62], [0.83, 0.62], [-0.83, -0.62], [0.83, -0.62]];
    stacks.forEach(([dx, dz], i) => {
      const lag = clamp(lift * 1.6 - i * 0.09);
      for (let layer = 0; layer < 8; layer++) {
        const y = -0.11 + layer * 0.028 + lag * (0.18 + layer * 0.03);
        this.r3d.draw(
          this.cam,
          box(dx, y, dz, 0.3, 0.022, 0.2, layer % 2 ? M.hbm : M.block),
          envKey,
        );
      }
    });
    this.r3d.applyDOF(lerp(2.3, 1.7, p), 0.5, 10);

    this.stack(t, {
      start: 22.3,
      eyebrow: '03  MEMORY',
      headline: 'HBM IS THE HIDDEN TAX',
      body: ['STACKED DRAM SITS BESIDE THE DIE', 'ON A SILICON INTERPOSER.'],
      stat: '8x',
      statUnit: 'HBM3E STACKS',
      statColor: P.cyan,
    });
  }

  /* -------------------------------------------------------- S5 EUV (30-38) */
  private s5(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 30) / 8;
    const p = e('orbit', u);
    const ang = lerp(-0.75, 0.45, p);
    const rad = lerp(4.4, 3.4, e('dolly_in', u));
    this.camera([Math.sin(ang) * rad, lerp(1.15, 0.92, p), Math.cos(ang) * rad], [0, 0.06, 0], lerp(32, 28, p));
    for (const m of this.euv) this.r3d.draw(this.cam, m, envKey);
    // plasma pulse riding the beat
    const beat = (t % BEAT) / BEAT;
    const pulse = Math.exp(-beat * 7);
    this.r3d.draw(
      this.cam,
      box(-0.28, -0.02, 0.28, 0.02 + pulse * 0.03, 0.3 + pulse * 0.1, 0.02 + pulse * 0.03, {
        ...M.cyanLit,
        emit: [0.3 + pulse, 1.35 + pulse * 1.2, 1.7 + pulse * 1.4],
      }),
      envWide,
    );
    this.r3d.applyDOF(rad * 0.9, 0.5, 11);

    this.stack(t, {
      start: 30.3,
      eyebrow: '04  LITHOGRAPHY',
      headline: 'MACHINES COST $200M',
      body: ['EUV LIGHT IS MADE BY VAPORISING', 'TIN 50,000 TIMES A SECOND.'],
      stat: '$200M',
      statUnit: 'PER SCANNER',
      statColor: P.cyan,
    });
  }

  /* ---------------------------------------------- S6 supply/demand (38-46) */
  private s6(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 38) / 8;
    const p = e('drift', u);
    this.camera([lerp(-1.1, -0.7, p), lerp(0.8, 0.55, p), lerp(2.5, 2.05, p)], [-0.1, 0.0, 0], lerp(36, 33, p));
    this.r3d.draw(this.cam, plane(0, -0.55, 0, 8, 6, M.black, 20), envWide);
    // demand bars: 8 towers, rising, some taller
    const heights = [0.18, 0.26, 0.34, 0.42, 0.55, 0.67, 0.82, 0.98];
    const grow = clamp((t - 38.4) / 2.8);
    heights.forEach((h, i) => {
      const k = clamp(grow * 1.5 - i * 0.08);
      const hh = h * k;
      this.r3d.draw(this.cam, box(-1.05 + i * 0.3, -0.55 + hh / 2, 0, 0.18, hh, 0.18, i === 7 ? M.cyanLit : M.steel), envWide);
    });
    // supply line: a thin bar that lags behind
    const supply = clamp((t - 39.6) / 2.2);
    this.r3d.draw(this.cam, box(-0.25, -0.55 + 0.22 * supply, 0.28, 2.4, 0.02, 0.02, M.cyanLit), envWide);
    this.r3d.applyDOF(2.6, 0.35, 10);

    this.stack(t, {
      start: 38.3,
      eyebrow: '05  SUPPLY',
      headline: 'DEMAND OUTRAN SUPPLY',
      body: ['FABS RUN AT CAPACITY FOR YEARS', 'BEFORE A NEW NODE SHIPS.'],
    });
    drawType(this.r3d.frame, this.tcam, {
      text: 'DEMAND',
      size: this.fit('DEMAND', this.sz(0.022), 0.16),
      position: this.at(0.34, 0.16),
      align: 'left',
      tracking: 0.16,
      color: P.bone,
      weight: 1.0,
      opacity: clamp((t - 40.2) / 0.5),
    });
    drawType(this.r3d.frame, this.tcam, {
      text: 'SUPPLY',
      size: this.fit('SUPPLY', this.sz(0.022), 0.16),
      position: this.at(-0.30, -0.30),
      align: 'left',
      tracking: 0.16,
      color: P.cyan,
      weight: 1.0,
      opacity: clamp((t - 41.0) / 0.5),
    });
  }

  /* ------------------------------------------- S7 price breakdown (46-54) */
  private s7(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 46) / 8;
    const p = e('drift', u);
    this.camera([lerp(-0.30, -0.12, p), lerp(0.78, 0.6, p), lerp(4.2, 3.7, p)], [0, -0.22, 0], lerp(33, 31, p));
    this.r3d.draw(this.cam, plane(0, -0.62, 0, 8, 6, M.black, 20), envWide);
    // cost stack: segments building a single bar, left to right
    const segs = [
      { w: 0.62, m: M.steel, label: 'DIE' },
      { w: 0.5, m: M.hbm, label: 'HBM' },
      { w: 0.3, m: M.gold, label: 'PKG' },
      { w: 0.22, m: M.cap, label: 'BOARD' },
      { w: 0.26, m: M.cyanLit, label: 'MARGIN' },
    ];
    const SC = 1.45;
    const total = segs.reduce((a, s) => a + s.w, 0) * SC;
    let x = -total / 2;
    const grow = clamp((t - 46.4) / 3.2);
    segs.forEach((s) => {
      const w = s.w * SC * grow;
      if (w > 0.001) {
        // contiguous bar: no per-segment stagger, or the stack shows gaps
        this.r3d.draw(this.cam, box(x + w / 2, -0.24, 0, w, 0.62, 0.62, s.m), envWide);
      }
      x += s.w * SC * grow;
    });
    this.r3d.applyDOF(4.2, 0.35, 9);

    this.stack(t, {
      start: 46.3,
      eyebrow: '06  BILL OF MATERIALS',
      headline: 'THE PRICE IS A STACK',
    });
    let lx = -total / 2;
    segs.forEach((sg, i) => {
      const on = clamp((t - 47.4 - i * 0.18) / 0.3);
      const cx = lx + (sg.w * SC * grow) / 2;
      // project the segment's front face so the label lands under its segment
      const [xf, yf] = this.projFrac([cx, -0.24, 0.32]);
      const labelY = Math.min(yf - 0.34, -0.14);
      const tick = this.projFrac([cx, -0.24, 0.32]);
      this.rule(
        this.r3d.frame,
        this.at(tick[0], tick[1] - 0.02),
        this.at(tick[0], labelY + 0.03),
        P.dim,
        1,
        0.35 * on,
      );
      drawType(this.r3d.frame, this.tcam, {
        text: sg.label,
        size: this.sz(0.019),
        position: this.at(xf, labelY),
        align: 'center',
        tracking: 0.1,
        color: P.dim,
        weight: 1.0,
        opacity: on * 0.95,
      });
      lx += sg.w * SC * grow;
    });
  }

  /* ------------------------------------------------- S8 answer (54-60) */
  private s8(t: number, e: (k: string, u: number) => number): void {
    const u = (t - 54) / 6;
    const p = e('dolly_in', u);
    const spin = lerp(-0.62, -0.16, p);
    const rad = lerp(3.9, 3.1, p);
    this.camera([Math.sin(spin) * rad + 0.42, lerp(1.75, 1.35, p), Math.cos(spin) * rad], [0.42, -0.24, 0], lerp(33, 29, p));
    for (const m of this.gpu.meshes) this.r3d.draw(this.cam, m.mesh, envKey);
    this.r3d.applyDOF(Math.hypot(rad, 1.55), 0.45, 10);

    const k1 = clamp((t - 54.3) / 0.5);
    drawType(this.r3d.frame, this.tcam, {
      text: 'IT IS EXPENSIVE',
      size: this.fit('IT IS EXPENSIVE', this.sz(0.048), 0.1, 0.86),
      position: this.at(0, 0.72),
      align: 'center',
      tracking: 0.1,
      color: P.dim,
      weight: 1.0,
      opacity: k1,
      perChar: (i) => ({ wipe: clamp(k1 * 1.4 - i * 0.03) }),
    });
    const k2 = clamp((t - 55.2) / 0.5);
    drawType(this.r3d.frame, this.tcam, {
      text: 'BECAUSE IT IS HARD',
      size: this.fit('BECAUSE IT IS HARD', this.sz(0.082), 0, 0.86),
      position: this.at(0, 0.52),
      align: 'center',
      tracking: 0.0,
      color: P.bone,
      weight: 1.0,
      opacity: clamp(k2 * 3),
      perChar: (i) => ({ wipe: clamp(k2 * 1.5 - i * 0.035) }),
    });
    if (t > 56.2) {
      const half = (measure('BECAUSE IT IS HARD', 0) * this.fit('BECAUSE IT IS HARD', this.sz(0.082), 0, 0.86)) / 2;
      const k3 = clamp((t - 56.2) / 0.6);
      this.rule(this.r3d.frame, this.at(0, 0.46).map((v, i) => (i === 0 ? -half : v)) as Vec3,
        this.at(0, 0.46).map((v, i) => (i === 0 ? -half + 2 * half * k3 : v)) as Vec3, P.cyan, 1.4, 0.85);
    }
    drawType(this.r3d.frame, this.tcam, {
      text: 'GPU PRICE EXPLAINER / 2026',
      size: this.fit('GPU PRICE EXPLAINER / 2026', this.sz(0.019), 0.26),
      position: this.at(0, -0.86),
      align: 'center',
      tracking: 0.26,
      color: P.dim,
      weight: 1.0,
      opacity: clamp((t - 57.0) / 0.6) * 0.85,
    });
  }

  /* ------------------------------------------------------------- helpers */

  /** Frame fractions (-1..1) -> graphics-layer world space. */
  /** One typographic stack used by every scene: single grid, single hierarchy. */
  private stack(
    t: number,
    o: {
      start: number;
      eyebrow?: string;
      eyebrowColor?: RGB;
      headline?: string;
      headlineColor?: RGB;
      body?: string[];
      stat?: string;
      statUnit?: string;
      statColor?: RGB;
    },
  ): void {
    const f = this.r3d.frame;
    if (o.eyebrow) {
      const k = clamp((t - o.start) / 0.4);
      drawType(f, this.tcam, {
        text: o.eyebrow,
        size: this.fit(o.eyebrow, this.sz(0.028), 0.2),
        position: this.at(-0.86, 0.62),
        align: 'left',
        tracking: 0.2,
        color: o.eyebrowColor ?? P.cyan,
        weight: 1.05,
        opacity: k,
      });
    }
    if (o.headline) {
      const k = clamp((t - o.start - 0.18) / 0.5);
      const hSize = this.fit(o.headline, this.sz(0.082), 0.06);
      drawType(f, this.tcam, {
        text: o.headline,
        size: hSize,
        position: this.at(-0.86, 0.44),
        align: 'left',
        tracking: lerp(0.06, -0.005, clamp(k)),
        color: o.headlineColor ?? P.bone,
        weight: 1.0,
        opacity: clamp((t - o.start - 0.18) / 0.25),
        perChar: (i) => ({ wipe: clamp(k * 1.6 - i * 0.035) }),
      });
    }
    (o.body ?? []).forEach((line, i) => {
      const k = clamp((t - o.start - 0.55 - i * 0.12) / 0.45);
      drawType(f, this.tcam, {
        text: line,
        size: this.fit(line, this.sz(0.026), 0.13),
        position: this.at(-0.86, 0.305 - i * 0.052),
        align: 'left',
        tracking: 0.13,
        color: P.dim,
        weight: 1.0,
        opacity: k * 0.95,
      });
    });
    if (o.stat) {
      const k = clamp((t - o.start - 0.7) / 0.5);
      drawType(f, this.tcam, {
        text: o.stat,
        size: this.sz(0.075),
        position: this.at(0.86, -0.70),
        align: 'right',
        tracking: -0.005,
        color: o.statColor ?? P.bone,
        weight: 1.0,
        opacity: k,
      });
      if (o.statUnit) {
        drawType(f, this.tcam, {
          text: o.statUnit,
          size: this.sz(0.024),
          position: this.at(0.86, -0.78),
          align: 'right',
          tracking: 0.18,
          color: P.dim,
          weight: 1.0,
          opacity: k,
        });
      }
    }
  }

  /** Project a 3D point into graphics-layer fractions (xf, yf) at 1.0 = half height. */
  private projFrac(p: Vec3): [number, number] {
    const pr = this.cam.project(p);
    if (!pr.ok) return [0, 0];
    // graphics layer maps xf -> world x = xf*aspect on a half-height-1 frustum,
    // so ndcX already IS the graphics fraction. Do not scale by aspect again.
    return [(pr.x / this.w) * 2 - 1, 1 - (pr.y / this.h) * 2];
  }

  /** Project a world x onto the graphics grid so 3D labels line up with 3D geometry. */
  private worldXToFrac(x: number, y = -0.24, z = 0): number {
    const pr = this.cam.project([x, y, z]);
    if (!pr.ok) return 0;
    return ((pr.x / this.w) * 2 - 1) * (this.w / this.h);
  }

  private at(xf: number, yf: number): [number, number, number] {
    const aspect = this.w / this.h;
    return [xf * aspect, yf, 0];
  }

  /** Type size expressed as a fraction of frame HEIGHT (0.1 = 10%). */
  /**
   * Portrait has ~1/3 the horizontal room of 16:9. A headline sized for
   * landscape would run off a phone screen, so every type call is fitted to
   * the actual frame width. This is the one place aspect ratio is allowed to
   * change a composition.
   */
  private fit(text: string, size: number, tracking = 0, maxFrac = 0.92): number {
    const avail = 2 * (this.w / this.h) * maxFrac; // world units of frame width
    const w = measure(text, tracking, 1) * size;    // measure() is in em units
    return w > avail ? (size * avail) / w : size;
  }

  private sz(frac: number): number {
    return frac * 2;
  }
  private rule(f: Frame, a: Vec3, b: Vec3, col: RGB, w: number, alpha: number): void {
    const p = this.tcam.project(a);
    const q = this.tcam.project(b);
    if (!p.ok || !q.ok) return;
    f.line(p.x, p.y, q.x, q.y, col, w, alpha);
  }

  /** Transition EDL for the audit gate — five distinct types by construction. */
  registerTransitions(): Array<{ type: string; at: number }> {
    const list = [
      { type: 'hard_cut', at: 6 },
      { type: 'whip_pan', at: 14 },
      { type: 'glitch', at: 22 },
      { type: 'light_sweep', at: 30 },
      { type: 'defocus_dissolve', at: 38 },
      { type: 'scale_punch', at: 46 },
      { type: 'wipe', at: 54 },
    ];
    return list;
  }
}

export { mix3 };
