/**
 * transitions.ts — six distinct transition types, applied as post passes at
 * the shot cuts. The audit gate (gates.ts) reads the EDL this file exports, so
 * "5+ unique transition types" is verified from data, not asserted in prose.
 */
import { Frame, sampleBilinear } from '../../motion/src/core/raster.ts';
import { clamp, hash2 } from '../../motion/src/core/math.ts';
import { blurFrame } from './engine3d.ts';

export type TransitionKind =
  | 'hard_cut'
  | 'whip_pan'
  | 'glitch'
  | 'light_sweep'
  | 'defocus_dissolve'
  | 'scale_punch'
  | 'wipe';

export interface Transition {
  kind: TransitionKind;
  at: number;
  /** seconds */
  dur: number;
}

export const EDL: Transition[] = [
  { kind: 'hard_cut', at: 6, dur: 0 },
  { kind: 'whip_pan', at: 14, dur: 0.2 },
  { kind: 'glitch', at: 22, dur: 0.16 },
  { kind: 'light_sweep', at: 30, dur: 0.3 },
  { kind: 'defocus_dissolve', at: 38, dur: 0.32 },
  { kind: 'scale_punch', at: 46, dur: 0.22 },
  { kind: 'wipe', at: 54, dur: 0.28 },
];

/** Apply whichever transition is active at time t. */
export function applyTransition(f: Frame, t: number): Frame {
  for (const tr of EDL) {
    if (tr.dur <= 0) continue;
    const u = (t - tr.at) / tr.dur;
    if (u < 0 || u > 1) continue;
    // strongest at the midpoint, so the cut itself is hidden
    const k = Math.sin(u * Math.PI);
    switch (tr.kind) {
      case 'whip_pan':
        return whipPan(f, k * 0.55);
      case 'glitch':
        return glitch(f, t, k);
      case 'light_sweep':
        return lightSweep(f, k, t);
      case 'defocus_dissolve':
        return defocus(f, k);
      case 'scale_punch':
        return scalePunch(f, k);
      case 'wipe':
        return wipe(f, k);
      default:
        return f;
    }
  }
  return f;
}

function whipPan(f: Frame, k: number): Frame {
  const out = new Frame(f.w, f.h);
  const dx = k * f.w * 0.09;
  for (let y = 0; y < f.h; y++) {
    // smear grows with distance from the pan axis
    const smear = (1 - Math.abs(y / f.h - 0.5) * 1.4) * k * 16;
    for (let x = 0; x < f.w; x++) {
      const o = (y * f.w + x) * 3;
      if (smear > 1.2) {
        let r = 0, g = 0, b = 0;
        const n = Math.min(12, Math.floor(smear));
        for (let s = 0; s < n; s++) {
          const sx = x + dx - (smear * s) / n;
          r += sampleBilinear(f, sx, y, 0);
          g += sampleBilinear(f, sx, y, 1);
          b += sampleBilinear(f, sx, y, 2);
        }
        out.data[o] = r / n;
        out.data[o + 1] = g / n;
        out.data[o + 2] = b / n;
      } else {
        out.data[o] = sampleBilinear(f, x + dx, y, 0);
        out.data[o + 1] = sampleBilinear(f, x + dx, y, 1);
        out.data[o + 2] = sampleBilinear(f, x + dx, y, 2);
      }
    }
  }
  return out;
}

function glitch(f: Frame, t: number, k: number): Frame {
  const out = new Frame(f.w, f.h);
  const rows = 60;
  const band = Math.ceil(f.h / rows);
  const frame = Math.floor(t * 40);
  for (let y = 0; y < f.h; y++) {
    const b = Math.floor(y / band);
    const n = hash2(b, frame);
    const shift = n > 0.62 ? (hash2(b * 3.1, frame) - 0.5) * f.w * 0.08 * k : 0;
    const drop = n > 0.93 && k > 0.4;
    for (let x = 0; x < f.w; x++) {
      const o = (y * f.w + x) * 3;
      if (drop) continue;
      out.data[o] = sampleBilinear(f, x - shift + k * 4, y, 0);
      out.data[o + 1] = sampleBilinear(f, x - shift, y, 1);
      out.data[o + 2] = sampleBilinear(f, x - shift - k * 4, y, 2);
    }
  }
  return out;
}

function lightSweep(f: Frame, k: number, t: number): Frame {
  const out = new Frame(f.w, f.h);
  out.data.set(f.data);
  const cx = f.w * (0.1 + 0.8 * ((t * 3) % 1));
  for (let x = 0; x < f.w; x++) {
    const d = Math.abs(x - cx) / (f.w * 0.22);
    const a = Math.exp(-d * d * 3) * k * 0.42;
    if (a < 0.002) continue;
    for (let y = 0; y < f.h; y++) {
      const o = (y * f.w + x) * 3;
      out.data[o] += 0.5 * a;
      out.data[o + 1] += 0.85 * a;
      out.data[o + 2] += 1.0 * a;
    }
  }
  return out;
}

function defocus(f: Frame, k: number): Frame {
  const b = blurFrame(f, 1 + k * 4);
  const out = new Frame(f.w, f.h);
  for (let i = 0; i < f.data.length; i++) out.data[i] = f.data[i] + (b.data[i] - f.data[i]) * Math.min(1, k * 1.25);
  return out;
}

function scalePunch(f: Frame, k: number): Frame {
  const out = new Frame(f.w, f.h);
  const s = 1 + k * 0.06;
  const cx = f.w / 2;
  const cy = f.h / 2;
  for (let y = 0; y < f.h; y++) {
    for (let x = 0; x < f.w; x++) {
      const sx = cx + (x - cx) / s;
      const sy = cy + (y - cy) / s;
      const o = (y * f.w + x) * 3;
      out.data[o] = sampleBilinear(f, sx, sy, 0);
      out.data[o + 1] = sampleBilinear(f, sx, sy, 1);
      out.data[o + 2] = sampleBilinear(f, sx, sy, 2);
    }
  }
  return out;
}

function wipe(f: Frame, k: number): Frame {
  const out = new Frame(f.w, f.h);
  out.data.set(f.data);
  const edge = f.w * clamp(k);
  for (let y = 0; y < f.h; y++) {
    for (let x = 0; x < f.w; x++) {
      const d = Math.abs(x - edge);
      if (d < f.w * 0.16) {
        const a = Math.exp(-((d / (f.w * 0.05)) ** 2)) * 0.55;
        const o = (y * f.w + x) * 3;
        out.data[o] += 0.35 * a;
        out.data[o + 1] += 0.9 * a;
        out.data[o + 2] += 1.0 * a;
      }
    }
  }
  return out;
}
