/**
 * raster.ts — a small HDR software rasteriser.
 *
 * Everything is drawn additively into a linear-light Float32 RGB buffer, which
 * is exactly how neon behaves in the real world: light adds, it never subtracts.
 * A final tone-map (exponential shoulder) is what turns raw intensity into the
 * filmic roll-off you see in high-end motion graphics.
 */

import { clamp, smoothstep } from './math.ts';

/** 8x8 Bayer threshold matrix, normalised to 0..1 — used for dithering. */
const BAYER8 = (() => {
  const b = new Float32Array(64);
  const base = [
    0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26,
    12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
    3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25,
    15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21,
  ];
  for (let i = 0; i < 64; i++) b[i] = base[i] / 64 - 0.5;
  return b;
})();

export type RGB = [number, number, number];

export class Frame {
  readonly w: number;
  readonly h: number;
  /** linear-light RGB, 3 floats per pixel */
  readonly data: Float32Array;

  constructor(w: number, h: number) {
    this.w = w;
    this.h = h;
    this.data = new Float32Array(w * h * 3);
  }

  clear(r = 0, g = 0, b = 0): void {
    const d = this.data;
    for (let i = 0; i < d.length; i += 3) {
      d[i] = r;
      d[i + 1] = g;
      d[i + 2] = b;
    }
  }

  /** Additive pixel write — no clipping, values are allowed to exceed 1.0. */
  addPx(x: number, y: number, c: RGB, a: number): void {
    const xi = x | 0;
    const yi = y | 0;
    if (xi < 0 || yi < 0 || xi >= this.w || yi >= this.h) return;
    const i = (yi * this.w + xi) * 3;
    this.data[i] += c[0] * a;
    this.data[i + 1] += c[1] * a;
    this.data[i + 2] += c[2] * a;
  }

  /**
   * Anti-aliased additive line.
   * Coverage comes from the analytic distance to the segment, so a 0.7px line
   * still reads as a crisp hairline instead of a broken staircase.
   */
  line(x0: number, y0: number, x1: number, y1: number, c: RGB, width = 1, intensity = 1): void {
    const dx = x1 - x0;
    const dy = y1 - y0;
    const half = width * 0.5;
    const pad = half + 1;
    const minX = Math.max(0, Math.floor(Math.min(x0, x1) - pad));
    const maxX = Math.min(this.w - 1, Math.ceil(Math.max(x0, x1) + pad));
    const minY = Math.max(0, Math.floor(Math.min(y0, y1) - pad));
    const maxY = Math.min(this.h - 1, Math.ceil(Math.max(y0, y1) + pad));
    if (minX > maxX || minY > maxY) return;

    const len2 = dx * dx + dy * dy || 1e-9;
    const d = this.data;

    for (let y = minY; y <= maxY; y++) {
      const py = y + 0.5;
      for (let x = minX; x <= maxX; x++) {
        const px = x + 0.5;
        let t = ((px - x0) * dx + (py - y0) * dy) / len2;
        t = t < 0 ? 0 : t > 1 ? 1 : t;
        const cx = x0 + dx * t - px;
        const cy = y0 + dy * t - py;
        const dist = Math.sqrt(cx * cx + cy * cy);
        // soft edge: fully covered inside the core, feathered over ~1.1px
        const cov = 1 - smoothstep((dist - half) / 1.1);
        if (cov <= 0.002) continue;
        const a = cov * intensity;
        const i = (y * this.w + x) * 3;
        d[i] += c[0] * a;
        d[i + 1] += c[1] * a;
        d[i + 2] += c[2] * a;
      }
    }
  }

  polyline(pts: Array<[number, number]>, c: RGB, width = 1, intensity = 1): void {
    for (let i = 1; i < pts.length; i++) {
      this.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], c, width, intensity);
    }
  }

  /** Smooth radial glow — the cheap physical stand-in for a bloom kernel. */
  glow(cx: number, cy: number, radius: number, c: RGB, intensity = 1, power = 2): void {
    const minX = Math.max(0, Math.floor(cx - radius));
    const maxX = Math.min(this.w - 1, Math.ceil(cx + radius));
    const minY = Math.max(0, Math.floor(cy - radius));
    const maxY = Math.min(this.h - 1, Math.ceil(cy + radius));
    const inv = 1 / radius;
    const d = this.data;
    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        const dx = (x + 0.5 - cx) * inv;
        const dy = (y + 0.5 - cy) * inv;
        const r2 = dx * dx + dy * dy;
        if (r2 >= 1) continue;
        const falloff = Math.pow(1 - Math.sqrt(r2), power);
        const a = falloff * intensity;
        const i = (y * this.w + x) * 3;
        d[i] += c[0] * a;
        d[i + 1] += c[1] * a;
        d[i + 2] += c[2] * a;
      }
    }
  }

  /** Filled axis-aligned rect with linear vertical gradient from c0 -> c1. */
  rectGradient(x0: number, y0: number, x1: number, y1: number, c0: RGB, c1: RGB, alpha = 1): void {
    const ax = Math.max(0, Math.floor(x0));
    const bx = Math.min(this.w - 1, Math.ceil(x1));
    const ay = Math.max(0, Math.floor(y0));
    const by = Math.min(this.h - 1, Math.ceil(y1));
    const span = Math.max(1e-6, y1 - y0);
    const d = this.data;
    for (let y = ay; y <= by; y++) {
      const t = clamp((y + 0.5 - y0) / span);
      const r = c0[0] + (c1[0] - c0[0]) * t;
      const g = c0[1] + (c1[1] - c0[1]) * t;
      const b = c0[2] + (c1[2] - c0[2]) * t;
      for (let x = ax; x <= bx; x++) {
        const i = (y * this.w + x) * 3;
        d[i] += r * alpha;
        d[i + 1] += g * alpha;
        d[i + 2] += b * alpha;
      }
    }
  }

  /** Add another frame, optionally scaled by `k` (used by the post stack). */
  add(other: Frame, k = 1): void {
    const a = this.data;
    const b = other.data;
    for (let i = 0; i < a.length; i++) a[i] += b[i] * k;
  }

  /**
   * Tone-map linear HDR -> 8-bit sRGB.
   * Exponential shoulder keeps highlights from clipping to flat white and
   * makes the bloom read as light instead of paint. An 8x8 Bayer threshold is
   * added before quantisation: without it, a near-black gradient bands badly.
   */
  toSRGB8(out: Uint8Array): void {
    const d = this.data;
    const n = this.w * this.h;
    for (let p = 0, i = 0, y = 0, x = 0; p < n; p++, i += 3) {
      const bayer = BAYER8[(y & 7) * 8 + (x & 7)];
      for (let c = 0; c < 3; c++) {
        const v = Math.max(0, d[i + c]);
        const t = 1 - Math.exp(-v * 1.35);
        const srgb = Math.pow(t, 1 / 2.2) * 255;
        out[i + c] = (srgb + bayer) | 0;
      }
      if (++x === this.w) {
        x = 0;
        y++;
      }
    }
  }
}

/** Bilinear sample of a linear-light frame (used by distortion / aberration). */
export function sampleBilinear(f: Frame, x: number, y: number, ch: number): number {
  const { w, h, data } = f;
  if (x < 0 || y < 0 || x >= w - 1 || y >= h - 1) return 0;
  const x0 = x | 0;
  const y0 = y | 0;
  const fx = x - x0;
  const fy = y - y0;
  const i00 = (y0 * w + x0) * 3 + ch;
  const i10 = i00 + 3;
  const i01 = i00 + w * 3;
  const i11 = i01 + 3;
  const a = data[i00] + (data[i10] - data[i00]) * fx;
  const b = data[i01] + (data[i11] - data[i01]) * fx;
  return a + (b - a) * fy;
}
