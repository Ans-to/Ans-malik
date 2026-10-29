/**
 * scene.ts — the film.
 *
 * Art direction: editorial dark. Warm near-black, bone-white display type at
 * architectural scale, one hot accent, hairline rules, and a single sparse
 * wireframe object used as a depth element — not as the subject.
 *
 * Everything is a pure function of t, and every beat-driven value comes from
 * the analysed soundtrack (see audio/analyze.ts), so the cut is musical rather
 * than merely timed.
 */

import { Frame, type RGB } from './core/raster.ts';
import * as FX from './core/fx.ts';
import { clamp, lerp, mix3, noise1, smoothstep, type Vec3 } from './core/math.ts';
import { easeInOutCubic, easeInOutExpo, easeOutBack, easeOutExpo, easeOutQuint, type Ease } from './core/easing.ts';
import { Camera, drawMesh } from './graphics/stage.ts';
import { icosphere, morph, type ShapeName } from './graphics/wire.ts';
import { drawType, measure, type CharState } from './graphics/type.ts';
import type { Analysis } from './audio/analyze.ts';

/* ------------------------------------------------------------------ palette */
/** Values > 1 are intentional: the buffer is linear HDR and only these bloom. */
export const C = {
  /** warm charcoal, not blue-black */
  ink: [0.010, 0.0095, 0.010] as RGB,
  bone: [0.86, 0.855, 0.83] as RGB,
  boneDim: [0.5, 0.49, 0.475] as RGB,
  /** the single accent: hot vermilion */
  accent: [1.25, 0.30, 0.045] as RGB,
  accentDim: [0.75, 0.18, 0.04] as RGB,
  /** used only for the mesh, and only faintly */
  steel: [0.34, 0.42, 0.52] as RGB,
};

export const DURATION = 8;

/* ------------------------------------------------------------------- state */
let ANA: Analysis | null = null;
let BEATS: Analysis['beats'] = [];

export const GLITCH_WINDOWS: Array<[number, number]> = [
  [1.98, 2.12],
  [3.46, 3.6],
  [5.5, 5.64],
];

export function glitchAmount(t: number): number {
  let g = 0;
  for (const [a, b] of GLITCH_WINDOWS) {
    if (t >= a && t <= b) g = Math.max(g, Math.sin(((t - a) / (b - a)) * Math.PI) ** 0.7 * 0.7);
  }
  return g;
}

/** 1 at a detected beat onset, decaying. */
function flash(t: number, decay = 16): number {
  let v = 0;
  for (const b of BEATS) {
    const d = t - b.t;
    if (d >= 0 && d < 0.9) v = Math.max(v, Math.exp(-d * decay));
  }
  return v;
}

/* --------------------------------------------------------------- camera rig */
interface Key {
  t: number;
  eye: Vec3;
  target: Vec3;
  ease?: Ease;
}

const CAMERA_KEYS: Key[] = [
  { t: 0.0, eye: [0, 0, 7.2], target: [0, 0, 0] },
  { t: 1.05, eye: [0, 0, 6.0], target: [0, 0.02, 0], ease: easeOutQuint },
  { t: 2.0, eye: [0.22, 0.06, 5.35], target: [0.18, 0.02, 0] },
  { t: 3.0, eye: [0.9, 0.02, 5.1], target: [0.5, 0.0, 0] },
  { t: 3.5, eye: [1.0, 0.0, 5.0], target: [0.55, 0.0, 0] },
  { t: 4.4, eye: [0.35, 0.0, 4.85], target: [0.3, 0.0, 0] },
  { t: 5.3, eye: [0.05, 0.02, 5.4], target: [0.1, 0, 0] },
  { t: 5.55, eye: [0.0, 0.02, 5.9], target: [0, 0, 0] },
  { t: 6.05, eye: [0.0, 0.0, 3.55], target: [0, 0.02, 0.1], ease: easeInOutExpo },
  { t: 6.9, eye: [0.0, 0.0, 4.9], target: [0, 0.01, 0] },
  { t: 7.35, eye: [0.0, 0.0, 5.7], target: [0, 0, 0] },
  { t: 8.0, eye: [0.0, 0.0, 6.1], target: [0, 0, 0] },
];

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
    out[c] =
      (2 * u3 - 3 * u2 + 1) * v0 +
      (u3 - 2 * u2 + u) * m0 +
      (-2 * u3 + 3 * u2) * v1 +
      (u3 - u2) * m1;
  }
  return out;
}

/* -------------------------------------------------------------------- film */

export interface FilmContext {
  w: number;
  h: number;
  analysis: Analysis;
}

export class Film {
  cam = new Camera([0, 0, 7], [0, 0, 0]);
  readonly w: number;
  readonly h: number;
  readonly A: Analysis;
  private sphere = icosphere(1);

  constructor(ctx: FilmContext) {
    this.w = ctx.w;
    this.h = ctx.h;
    this.A = ctx.analysis;
    ANA = ctx.analysis;
    BEATS = ctx.analysis.beats;
    this.cam.resize(ctx.w, ctx.h);
    this.cam.fov = (42 * Math.PI) / 180;
  }

  /** World units -> pixels, used to lay type out in screen space. */
  private px(): number {
    return this.cam.scaleAt(6) || 1;
  }

  private updateCamera(t: number): void {
    const punch = this.A.punch(t, 11);
    const gl = glitchAmount(t);
    const eye = keyedVec(CAMERA_KEYS, 'eye', t);
    const target = keyedVec(CAMERA_KEYS, 'target', t);
    const sh = punch * 0.012 + gl * 0.05;
    this.cam.eye = [eye[0] + noise1(t * 23) * sh, eye[1] + noise1(t * 31 + 7) * sh, eye[2]];
    this.cam.target = [target[0] + noise1(t * 23) * sh * 0.5, target[1] + noise1(t * 31 + 7) * sh * 0.5, target[2]];
    this.cam.roll = noise1(t * 1.3) * 0.004;
    this.cam.update();
  }

  render(t: number): Frame {
    this.updateCamera(t);
    const f = new Frame(this.w, this.h);
    this.background(f, t);
    this.sceneA(f, t);
    this.sceneB(f, t);
    this.sceneC(f, t);
    this.sceneD(f, t);
    this.sceneE(f, t);
    this.hud(f, t);
    return f;
  }

  /* ----------------------------------------------------------- background */
  private background(f: Frame, t: number): void {
    f.clear(C.ink[0], C.ink[1], C.ink[2]);
    // a single soft pool of light, off-centre, that drifts with the camera
    const e = this.A.rmsAt(t);
    const cx = f.w * (0.5 + (this.cam.eye[0] - 0.3) * 0.06);
    const cy = f.h * 0.44;
    f.glow(cx, cy, f.h * 0.95, [0.030, 0.027, 0.024], 0.85 + e * 0.25, 2.6);
    // warm bounce from below (the accent, heavily diffused)
    f.glow(f.w * 0.5, f.h * 1.05, f.h * 0.7, [0.045, 0.014, 0.006], 0.5, 2.8);
  }

  /* -------------------------------------------------------------- helpers */

  /** A hairline rule in world space. */
  private rule(f: Frame, a: Vec3, b: Vec3, col: RGB, w = 1, alpha = 1): void {
    const p = this.cam.project(a);
    const q = this.cam.project(b);
    if (!p.ok || !q.ok) return;
    f.line(p.x, p.y, q.x, q.y, col, w, alpha);
  }

  /* ------------------------------------------------- scene A: the first line */
  private sceneA(f: Frame, t: number): void {
    if (t >= 2.0) return;
    const inA = clamp((t - 0.10) / 0.55);
    const outA = clamp((t - 1.86) / 0.14);
    const op = (1 - outA);
    const punch = this.A.punch(t, 12);
    const beat = ((t % this.A.beat) / this.A.beat);

    // a single hairline rule spans the frame at 1/3 height
    const ruleY = 0.06;
    const draw = easeOutQuint(clamp((t - 0.04) / 0.75));
    if (draw > 0) {
      this.rule(f, [-6 * draw, ruleY, 0], [6 * draw, ruleY, 0], C.bone, 1, 0.34 * op);
      this.rule(f, [-6 * draw * 0.999, ruleY - 0.001, 0], [6 * draw * 0.999, ruleY - 0.001, 0], C.accent, 1, 0.5 * op);
    }

    // MOTION rises out of the rule: the bottom of the glyphs appears first
    const size = 1.12;
    const rise = easeOutQuint(clamp((t - 0.12) / 0.95));
    const track = lerp(0.16, -0.035, easeOutQuint(clamp((t - 0.1) / 1.5)));
    drawType(f, this.cam, {
      text: 'MOTION',
      size,
      position: [0, ruleY + 0.035, 0],
      align: 'center',
      tracking: track,
      color: C.bone,
      weight: 1.0,
      opacity: op,
      fog: 0.7,
      emissive: 0.94 + punch * 0.1,
      perChar: (i) => ({
        scale: 1 + punch * 0.012,
        offset: [0, 0, 0],
        reveal: clamp(rise * 1.15 - i * 0.02),
      }),
    });

    // caption under the baseline, on the second beat
    const capK = easeOutExpo(clamp((t - 0.92) / 0.5));
    if (capK > 0) {
      drawType(f, this.cam, {
        text: 'A FILM WRITTEN IN TYPESCRIPT',
        size: 0.115,
        position: [0, ruleY - 0.235, 0],
        align: 'center',
        tracking: 0.14 + (1 - capK) * 0.1,
        color: C.boneDim,
        weight: 1.05,
        opacity: op * capK,
        condense: 0.94,
      });
      // accent tick that rides the beat next to the caption
      const tw = measure('A FILM WRITTEN IN TYPESCRIPT', 0.14, 0.94) * 0.115;
      const tickX = tw / 2 + 0.16;
      this.rule(
        f,
        [tickX, ruleY - 0.18, 0],
        [tickX + 0.045 * (0.4 + 0.6 * (1 - beat)), ruleY - 0.18, 0],
        C.accent,
        2,
        op * capK,
      );
    }

    // bottom-left credit block: balances the negative space above the headline
    const credK = easeOutExpo(clamp((t - 1.05) / 0.5));
    if (credK > 0) {
      drawType(f, this.cam, {
        text: 'TYPESCRIPT / NO GPU',
        size: 0.058,
        position: [-2.16, -1.12, 0],
        align: 'left',
        tracking: 0.2,
        color: C.boneDim,
        weight: 1,
        opacity: op * credK * 0.75,
      });
      drawType(f, this.cam, {
        text: '2026',
        size: 0.058,
        position: [2.16, -1.12, 0],
        align: 'right',
        tracking: 0.2,
        color: C.accent,
        weight: 1,
        opacity: op * credK * 0.8,
      });
      this.rule(f, [-2.16, -1.19, 0], [2.16, -1.19, 0], C.bone, 1, op * credK * 0.14);
    }

    // scrubber that fills across the frame as the bar resolves
    const scrub = clamp((t - 1.15) / 0.7);
    if (scrub > 0) {
      this.rule(f, [-2.2, ruleY, 0], [-2.2 + 4.4 * scrub, ruleY, 0], C.accent, 1.6, op * 0.9);
    }
  }

  /* ------------------------------------------- scene B: editorial + wireframe */
  private sceneB(f: Frame, t: number): void {
    if (t < 2.0 || t >= 3.5) return;
    const inK = easeOutQuint(clamp((t - 2.02) / 0.5));
    const out = clamp((t - 3.36) / 0.12);
    const op = inK * (1 - out);
    const punch = this.A.punch(t, 12);

    // sparse wireframe: barely-there geometry giving the frame depth
    const m = morph(this.sphere, 'sphere', 'octa', smoothstep(clamp((t - 2.2) / 1.3)), 1.0);
    drawMesh(f, this.cam, m, C.steel, {
      position: [2.45, 0.0, -2.9],
      rotation: [0.4 + t * 0.18, t * 0.4, 0.1],
      opacity: 0.22 * op,
      weight: 1.0,
      fog: 1.1,
      scale: 2.0 + punch * 0.02,
    });

    // index + label, left aligned on a grid
    const left = -2.16;
    drawType(f, this.cam, {
      text: '01',
      size: 0.1,
      position: [left, 0.80, 0],
      align: 'left',
      tracking: 0.1,
      color: C.accent,
      weight: 1.05,
      opacity: op,
    });
    this.rule(f, [left + 0.24, 0.845, 0], [left + 0.24 + 1.5 * inK, 0.845, 0], C.bone, 1, 0.22 * op);
    drawType(f, this.cam, {
      text: 'KINETIC',
      size: 0.44,
      position: [left, 0.10, 0],
      align: 'left',
      tracking: -0.01,
      color: C.bone,
      weight: 1.0,
      opacity: op,
      emissive: 0.86 + punch * 0.08,
      perChar: (i): CharState => {
        const k = easeOutQuint(clamp((t - 2.06 - i * 0.03) / 0.45));
        return { offset: [lerp(-0.22, 0, k), 0, 0], opacity: clamp((t - 2.04) / 0.12), wipe: k };
      },
    });
    drawType(f, this.cam, {
      text: 'TYPOGRAPHY',
      size: 0.44,
      position: [left, -0.42, 0],
      align: 'left',
      tracking: -0.01,
      color: C.accent,
      weight: 1.0,
      opacity: op,
      perChar: (i): CharState => {
        const k = easeOutQuint(clamp((t - 2.18 - i * 0.026) / 0.45));
        return { offset: [lerp(-0.22, 0, k), 0, 0], opacity: clamp((t - 2.16) / 0.12), wipe: k };
      },
    });

    // caption block bottom-left
    drawType(f, this.cam, {
      text: 'EVERY KEYFRAME IS A FUNCTION OF TIME',
      size: 0.088,
      position: [left, -0.78, 0],
      align: 'left',
      tracking: 0.1,
      color: C.boneDim,
      weight: 1,
      condense: 0.95,
      opacity: easeOutExpo(clamp((t - 2.55) / 0.4)) * op,
    });
  }

  /* --------------------------------------------- scene C: three-line stack */
  private sceneC(f: Frame, t: number): void {
    if (t < 3.5 || t >= 5.5) return;
    const out = clamp((t - 5.36) / 0.14);
    const op = (1 - out);
    const punch = this.A.punch(t, 12);

    const left = -2.16;
    const lines: Array<{ text: string; size: number; col: RGB; y: number; dir: number; start: number }> = [
      { text: 'PIXELS', size: 0.62, col: C.bone, y: 0.62, dir: 1, start: 3.54 },
      { text: 'OVER', size: 0.62, col: C.accent, y: -0.04, dir: -1, start: 3.72 },
      { text: 'TIME', size: 0.62, col: C.bone, y: -0.70, dir: 1, start: 3.9 },
    ];

    for (let li = 0; li < lines.length; li++) {
      const L = lines[li];
      const k = easeOutQuint(clamp((t - L.start) / 0.5));
      if (k <= 0) continue;
      drawType(f, this.cam, {
        text: L.text,
        size: L.size,
        position: [left + (1 - k) * 0.55 * L.dir, L.y, 0],
        align: 'left',
        tracking: -0.012,
        color: L.col,
        weight: 1.0,
        opacity: op * clamp((t - L.start) / 0.1),
        emissive: 0.92 + punch * 0.12,
        perChar: (i): CharState => {
          const ck = easeOutQuint(clamp((t - L.start - 0.04 - i * 0.028) / 0.4));
          return {
            offset: [lerp(0.3 * L.dir, 0, ck), 0, 0],
            opacity: clamp((t - L.start - i * 0.02) / 0.1),
            wipe: ck,
          };
        },
      });
      // leader rule: continues the baseline to the right, like a contents page
      const lw = measure(L.text, -0.012) * L.size;
      const ly = L.y + 0.02;
      this.rule(f, [left + lw + 0.16, ly, 0], [left + lw + 0.16 + 0.85 * k, ly, 0], li === 1 ? C.accent : C.bone, 1, op * (li === 1 ? 0.55 : 0.22));
      f.glow(
        ...(() => {
          const p0 = this.cam.project([left + lw + 0.16, ly, 0]);
          return [p0.x, p0.y] as [number, number];
        })(),
        3.2,
        li === 1 ? C.accent : C.bone,
        op * 0.5,
        2,
      );
    }

    // ticker across the bottom: small caps sliding left forever
    const tickerY = 1.28;
    const tickerText = 'MOTION DESIGN IN CODE   ·   NO TIMELINE   ·   NO PLUGINS   ·   ';
    const tw = measure(tickerText, 0.16, 0.92) * 0.072;
    const speed = 0.42;
    const phase = -(t * speed) % tw;
    const tickOp = easeOutExpo(clamp((t - 4.15) / 0.4)) * op;
    if (tickOp > 0.01) {
      for (let rep = 0; rep < 3; rep++) {
        const x = -2.4 + phase + rep * tw;
        if (x > 2.6 || x + tw < -2.6) continue;
        drawType(f, this.cam, {
          text: tickerText,
          size: 0.072,
          position: [x, tickerY, 0],
          align: 'left',
          tracking: 0.16,
          condense: 0.92,
          color: C.boneDim,
          weight: 1,
          opacity: tickOp * 0.6,
        });
      }
      this.rule(f, [-2.4, tickerY - 0.075, 0], [2.4, tickerY - 0.075, 0], C.bone, 1, tickOp * 0.16);
    }

    // index numeral far right, thin and large, purely compositional
    drawType(f, this.cam, {
      text: '03',
      size: 0.9,
      position: [2.72, 0.62, -1.4],
      align: 'right',
      tracking: 0.0,
      color: C.bone,
      weight: 0.55,
      opacity: op * 0.07,
      fog: 1.2,
    });
  }

  /* -------------------------------------------------- scene D: the drop */
  private sceneD(f: Frame, t: number): void {
    if (t < 5.5 || t >= 7.05) return;
    const inK = clamp((t - 5.5) / 0.12);
    const out = clamp((t - 6.94) / 0.11);
    const op = easeOutExpo(inK) * (1 - out);
    if (op <= 0.004) return;
    const drop = 5.98;
    const punch = this.A.punch(t, 9);
    const since = t - drop;

    // impact energy: elastic settle for the first ~0.6 s, then beat pulses
    const land = clamp(since / 0.7);
    const elastic = since > 0 ? 1 + 0.14 * Math.exp(-since * 6.5) * Math.cos(since * 26) : 1;
    const scale = lerp(1.34, 1, easeOutQuint(clamp(since / 0.5))) * elastic * (1 + punch * 0.005);

    // Motion smear: the word redrawn a few times along the vertical axis of the
    // impact. Offsets only — per-glyph scaling reads as a drop shadow.
    const trailK = since > 0 ? Math.max(0, 1 - since * 15) : 0;
    for (let i = 3; i >= 1; i--) {
      const k = i / 3;
      drawType(f, this.cam, {
        text: 'MOTION',
        size: 0.82,
        position: [0, 0.04 + k * 0.045, 0],
        align: 'center',
        tracking: -0.03,
        color: C.bone,
        weight: 1.0,
        opacity: op * trailK * 0.16 * (1 - k * 0.6),
        fog: 0.7,
        emissive: 0.6,
        perChar: (): CharState => ({ scale }),
      });
    }

    drawType(f, this.cam, {
      text: 'MOTION',
      size: 0.82,
      position: [0, 0.04, 0],
      align: 'center',
      tracking: -0.03,
      color: C.bone,
      weight: 1.0,
      opacity: op,
      fog: 0.7,
      emissive: 0.86 + punch * 0.08,
      perChar: (): CharState => ({
        scale,
        offset: [0, 0, 0],
      }),
    });

    // accent rule that snaps in on the drop, under the wordmark
    const barK = easeOutQuint(clamp(since / 0.35));
    if (barK > 0) {
      this.rule(f, [-1.32 * barK, -0.135, 0], [1.32 * barK, -0.135, 0], C.accent, 1.8, op * 0.85);
    }
    drawType(f, this.cam, {
      text: 'BY CODE',
      size: 0.13,
      position: [0, -0.30, 0],
      align: 'center',
      tracking: 0.5,
      color: C.boneDim,
      weight: 1.05,
      opacity: easeOutExpo(clamp((since - 0.12) / 0.3)) * op,
    });

    // lens flare strip on the initial impact only
    const flare = Math.max(0, 1 - since * 5);
    if (flare > 0) {
      const y = 0.06;
      this.rule(f, [-6, y, 0.4], [6, y, 0.4], C.accent, 2.2, flare * 0.42);
    }
  }

  /* ------------------------------------------------------ scene E: end card */
  private sceneE(f: Frame, t: number): void {
    if (t < 7.0) return;
    const k = clamp((t - 7.0) / 0.5);
    const e = easeOutQuint(k);
    const op = e;

    drawType(f, this.cam, {
      text: 'MOTION BY CODE',
      size: 0.3,
      position: [0, -0.12, 0],
      align: 'center',
      tracking: lerp(0.34, 0.16, e),
      color: C.bone,
      weight: 1.0,
      opacity: op,
      perChar: (i): CharState => ({ wipe: clamp(k * 1.3 - i * 0.02) }),
    });
    const w = measure('MOTION BY CODE', lerp(0.34, 0.16, e)) * 0.3;
    this.rule(f, [-w / 2, -0.24, 0], [w / 2, -0.24, 0], C.accent, 1.4, op * 0.8);
    drawType(f, this.cam, {
      text: 'ANS MALIK / 2026',
      size: 0.068,
      position: [0, -0.42, 0],
      align: 'center',
      tracking: 0.28,
      color: C.boneDim,
      weight: 1,
      opacity: easeOutExpo(clamp((t - 7.25) / 0.4)) * 0.9,
    });
  }

  /* ------------------------------------------------------------------ HUD */
  private hud(f: Frame, t: number): void {
    // corner marks: thin, low contrast, giving the frame a print feel
    const m = 40;
    const len = 18;
    const op = 0.16 * smoothstep(clamp(t / 0.5));
    const corners: Array<[number, number, number, number]> = [
      [m, m, 1, 1],
      [this.w - m, m, -1, 1],
      [m, this.h - m, 1, -1],
      [this.w - m, this.h - m, -1, -1],
    ];
    for (const [x, y, sx, sy] of corners) {
      f.line(x, y, x + len * sx, y, C.bone, 1, op);
      f.line(x, y, x, y + len * sy, C.bone, 1, op);
    }
    // frame counter, bottom left
    const frameNo = Math.round(t * 30);
    const label = `${String(Math.floor(frameNo / 30)).padStart(2, '0')}:${String(frameNo % 30).padStart(2, '0')}`;
    this.hudText(f, label, m + 1, this.h - m - 13, 0.55 * op + 0.08);
    this.hudText(f, `${this.A.bpm.toFixed(0)} BPM`, this.w - m - measure(`${this.A.bpm.toFixed(0)} BPM`, 0.14) * 9, m + 4, 0.45 * op + 0.06);
  }

  /**
   * Screen-space micro type. The camera looks down -Z with no roll, so the
   * screen -> world mapping on the z=0 plane is exact and cheap.
   */
  private hudText(f: Frame, text: string, x: number, y: number, op: number): void {
    const origin = this.cam.project([0, 0, 0]);
    const scale = this.cam.scaleAt(origin.depth);
    const sizeWorld = 9 / scale;
    const wx = (x - origin.x) / scale;
    // y is the TOP of the text; the glyph box grows upward from its position
    const wy = (this.h * 0.5 - (y + 9)) / scale;
    drawType(f, this.cam, {
      text,
      size: sizeWorld,
      position: [wx, wy, 0],
      align: 'left',
      tracking: 0.14,
      color: C.bone,
      weight: 1.15,
      opacity: op,
    });
  }
}

/* ------------------------------------------------------------- finishing */

export interface PostOptions {
  bloom?: number;
  aberration?: number;
  grain?: number;
  vignette?: number;
}

/**
 * Post stack, tuned for editorial clarity rather than neon:
 * light bloom on hot values only, a whisker of aberration, film grain,
 * and a gentle vignette. No scanlines, no chromatic mess.
 */
export function postProcess(f: Frame, t: number, glitchAmt: number, o: PostOptions = {}): Frame {
  let out = f;
  const gl = glitchAmt;
  if (gl > 0.001) out = FX.glitch(out, { amount: gl * 0.75, t });
  out = FX.chromaticAberration(out, (o.aberration ?? 0.35) + gl * 5);
  out = FX.bloom(out, { threshold: 0.95, radius: 5, intensity: o.bloom ?? 0.32, wide: 0.3 });
  FX.vignette(out, o.vignette ?? 0.5, 2.3);
  FX.grain(out, t, o.grain ?? 0.004);
  return out;
}

export { mix3, easeInOutCubic, easeOutBack };
