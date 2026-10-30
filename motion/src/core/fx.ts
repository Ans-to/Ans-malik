/**
 * fx.ts — the post-processing stack you would normally ship as shaders.
 *
 * Implemented on the CPU so the whole pipeline runs headless with no GPU:
 *   bright-pass -> multi-scale blur -> bloom
 *   radial chromatic aberration (RGB split)
 *   datamosh / block glitch
 *   scanlines, vignette, film grain, lens distortion, fades
 */

import { hash2, clamp, lerp } from './math.ts';
import { Frame, sampleBilinear, type RGB } from './raster.ts';

export function downsample(src: Frame, factor = 2): Frame {
  const w = Math.max(1, Math.floor(src.w / factor));
  const h = Math.max(1, Math.floor(src.h / factor));
  const dst = new Frame(w, h);
  const inv = 1 / (factor * factor);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let r = 0, g = 0, b = 0;
      for (let sy = 0; sy < factor; sy++) {
        for (let sx = 0; sx < factor; sx++) {
          const i = ((y * factor + sy) * src.w + (x * factor + sx)) * 3;
          r += src.data[i];
          g += src.data[i + 1];
          b += src.data[i + 2];
        }
      }
      const o = (y * w + x) * 3;
      dst.data[o] = r * inv;
      dst.data[o + 1] = g * inv;
      dst.data[o + 2] = b * inv;
    }
  }
  return dst;
}

/** 3-pass box blur ~= gaussian. Separable, O(n) per pass. */
export function blur(src: Frame, radius: number, passes = 3): Frame {
  const r = Math.max(1, Math.round(radius));
  let cur = new Frame(src.w, src.h);
  cur.data.set(src.data);
  let tmp = new Frame(src.w, src.h);

  for (let p = 0; p < passes; p++) {
    // horizontal
    for (let y = 0; y < cur.h; y++) {
      const row = y * cur.w * 3;
      for (let c = 0; c < 3; c++) {
        let sum = 0;
        for (let k = -r; k <= r; k++) {
          const x = clamp(k, 0, cur.w - 1) | 0;
          sum += cur.data[row + x * 3 + c];
        }
        const norm = 1 / (2 * r + 1);
        for (let x = 0; x < cur.w; x++) {
          tmp.data[row + x * 3 + c] = sum * norm;
          const addX = (x + r + 1 < cur.w ? x + r + 1 : cur.w - 1) * 3 + c;
          const subX = (x - r >= 0 ? x - r : 0) * 3 + c;
          sum += cur.data[row + addX] - cur.data[row + subX];
        }
      }
    }
    // vertical
    for (let x = 0; x < cur.w; x++) {
      for (let c = 0; c < 3; c++) {
        let sum = 0;
        for (let k = -r; k <= r; k++) {
          const y = clamp(k, 0, cur.h - 1) | 0;
          sum += tmp.data[(y * cur.w + x) * 3 + c];
        }
        const norm = 1 / (2 * r + 1);
        for (let y = 0; y < cur.h; y++) {
          cur.data[(y * cur.w + x) * 3 + c] = sum * norm;
          const addY = (y + r + 1 < cur.h ? y + r + 1 : cur.h - 1) * cur.w * 3 + x * 3 + c;
          const subY = (y - r >= 0 ? y - r : 0) * cur.w * 3 + x * 3 + c;
          sum += tmp.data[addY] - tmp.data[subY];
        }
      }
    }
    tmp = new Frame(src.w, src.h);
  }
  return cur;
}

/** Extract only the light that is "blowing out" — the part that should glow. */
export function brightPass(src: Frame, threshold = 0.35, knee = 0.4): Frame {
  const dst = new Frame(src.w, src.h);
  for (let i = 0; i < src.data.length; i += 3) {
    for (let c = 0; c < 3; c++) {
      const v = src.data[i + c];
      const k = clamp((v - threshold) / knee);
      dst.data[i + c] = v * k * k;
    }
  }
  return dst;
}

export interface BloomOptions {
  threshold?: number;
  radius?: number;
  intensity?: number;
  /** second, wider halo for the "cheap anamorphic" feel */
  wide?: number;
}

/** Multi-scale bloom, added back in linear light. */
export function bloom(src: Frame, opt: BloomOptions = {}): Frame {
  const { threshold = 0.3, radius = 6, intensity = 0.85, wide = 0.5 } = opt;
  const half = downsample(src, 2);
  const bright = brightPass(half, threshold);
  const tight = blur(bright, radius, 3);
  const broad = blur(downsample(bright, 2), radius * 1.6, 3);

  const out = new Frame(src.w, src.h);
  out.data.set(src.data);
  for (let y = 0; y < src.h; y++) {
    const hy = Math.min(half.h - 1, (y / 2) | 0);
    const by = Math.min(broad.h - 1, (y / 4) | 0);
    for (let x = 0; x < src.w; x++) {
      const hx = Math.min(half.w - 1, (x / 2) | 0);
      const bx = Math.min(broad.w - 1, (x / 4) | 0);
      const hi = (hy * half.w + hx) * 3;
      const bi = (by * broad.w + bx) * 3;
      const oi = (y * src.w + x) * 3;
      for (let c = 0; c < 3; c++) {
        out.data[oi + c] += tight.data[hi + c] * intensity + broad.data[bi + c] * intensity * wide;
      }
    }
  }
  return out;
}

/** Radial RGB split — strongest at the edges, like a real anamorphic lens. */
export function chromaticAberration(src: Frame, amount: number): Frame {
  if (amount <= 1e-4) return src;
  const dst = new Frame(src.w, src.h);
  const cx = src.w / 2;
  const cy = src.h / 2;
  for (let y = 0; y < src.h; y++) {
    for (let x = 0; x < src.w; x++) {
      const dx = (x - cx) / src.w;
      const dy = (y - cy) / src.h;
      const d = Math.hypot(dx, dy);
      const k = amount * (0.35 + d * 1.65);
      const o = (y * src.w + x) * 3;
      dst.data[o] = sampleBilinear(src, x + dx * k, y + dy * k, 0);
      dst.data[o + 1] = sampleBilinear(src, x, y, 1);
      dst.data[o + 2] = sampleBilinear(src, x - dx * k, y - dy * k, 2);
    }
  }
  return dst;
}

/** Barrel/pincushion distortion — subtle, sells the "real lens" feel. */
export function lensDistort(src: Frame, k: number): Frame {
  if (Math.abs(k) < 1e-4) return src;
  const dst = new Frame(src.w, src.h);
  const cx = src.w / 2;
  const cy = src.h / 2;
  for (let y = 0; y < src.h; y++) {
    for (let x = 0; x < src.w; x++) {
      const nx = (x - cx) / cx;
      const ny = (y - cy) / cy;
      const r2 = nx * nx + ny * ny;
      const f = 1 + k * r2;
      const sx = cx + nx * f * cx;
      const sy = cy + ny * f * cy;
      const o = (y * src.w + x) * 3;
      for (let c = 0; c < 3; c++) dst.data[o + c] = sampleBilinear(src, sx, sy, c);
    }
  }
  return dst;
}

export interface GlitchOptions {
  /** 0..1 — how destroyed the frame is */
  amount: number;
  /** time-varying seed so the glitch is alive */
  t: number;
  /** vertical position of the tear band (0..1) */
  focus?: number;
}

/** Horizontal block displacement + per-band RGB separation + dropped scanlines. */
export function glitch(src: Frame, opt: GlitchOptions): Frame {
  const { amount, t } = opt;
  if (amount <= 1e-4) return src;
  const dst = new Frame(src.w, src.h);
  const rows = 42;
  const rowH = Math.ceil(src.h / rows);

  for (let y = 0; y < src.h; y++) {
    const band = Math.floor(y / rowH);
    const n = hash2(band, Math.floor(t * 24));
    const active = n > 0.55 - amount * 0.45;
    const shift = active ? (hash2(band * 3.1, Math.floor(t * 24)) - 0.5) * src.w * 0.16 * amount : 0;
    const split = active ? (hash2(band * 7.7, Math.floor(t * 24) + 5) - 0.5) * 22 * amount : 0;
    const dropRow = active && hash2(band, 91) > 0.86;

    for (let x = 0; x < src.w; x++) {
      const o = (y * src.w + x) * 3;
      if (dropRow) continue;
      const sx = x - shift;
      dst.data[o] = sampleBilinear(src, sx + split, y, 0);
      dst.data[o + 1] = sampleBilinear(src, sx, y, 1);
      dst.data[o + 2] = sampleBilinear(src, sx - split, y, 2);
    }
  }

  // block corruption: a few hard-edged rectangles sampled from elsewhere
  const blocks = Math.floor(amount * 7);
  for (let i = 0; i < blocks; i++) {
    const bx = hash2(i, Math.floor(t * 15)) * src.w;
    const by = hash2(i + 20, Math.floor(t * 15)) * src.h;
    const bw = 30 + hash2(i + 40, 3) * src.w * 0.16 * amount;
    const bh = 6 + hash2(i + 60, 4) * src.h * 0.05;
    const ox = (hash2(i + 80, Math.floor(t * 15)) - 0.5) * src.w * 0.2;
    for (let y = Math.floor(by); y < Math.min(src.h, by + bh); y++) {
      for (let x = Math.floor(bx); x < Math.min(src.w, bx + bw); x++) {
        if (x < 0 || y < 0) continue;
        const o = (y * src.w + x) * 3;
        const sx = clamp(x + ox, 0, src.w - 2);
        dst.data[o] = sampleBilinear(src, sx, y, 0);
        dst.data[o + 1] = sampleBilinear(src, sx, y, 1) * 0.9;
        dst.data[o + 2] = sampleBilinear(src, sx, y, 2) * 1.1;
      }
    }
  }
  return dst;
}

/** CRT-style horizontal lines + a slow rolling refresh bar. */
export function scanlines(src: Frame, t: number, period = 3, amount = 0.12): void {
  const d = src.data;
  const rollY = ((t * 0.33) % 1) * src.h;
  for (let y = 0; y < src.h; y++) {
    const line = y % period === 0 ? 1 - amount : 1;
    const dist = Math.abs(y - rollY);
    const roll = dist < src.h * 0.09 ? 1 + 0.055 * (1 - dist / (src.h * 0.09)) : 1;
    const k = line * roll;
    if (k === 1) continue;
    for (let x = 0; x < src.w; x++) {
      const i = (y * src.w + x) * 3;
      d[i] *= k;
      d[i + 1] *= k;
      d[i + 2] *= k;
    }
  }
}

export function vignette(src: Frame, amount = 0.55, power = 2.2): void {
  const d = src.data;
  const cx = src.w / 2;
  const cy = src.h / 2;
  const maxR = Math.hypot(cx, cy);
  for (let y = 0; y < src.h; y++) {
    for (let x = 0; x < src.w; x++) {
      const r = Math.hypot(x - cx, y - cy) / maxR;
      const k = 1 - amount * Math.pow(clamp((r - 0.35) / 0.65), power);
      const i = (y * src.w + x) * 3;
      d[i] *= k;
      d[i + 1] *= k;
      d[i + 2] *= k;
    }
  }
}

/**
 * Film grain in linear light.
 * Generated at half resolution and bilinearly upsampled: real grain clumps,
 * and per-pixel noise is both unrealistic and a codec's worst nightmare
 * (it accounts for ~40 Mb/s of bitrate on its own).
 */
export function grain(src: Frame, t: number, amount = 0.005): void {
  const d = src.data;
  const seed = Math.floor(t * 48);
  const hw = Math.ceil(src.w / 2) + 1;
  const hh = Math.ceil(src.h / 2) + 1;
  const field = new Float32Array(hw * hh);
  for (let y = 0; y < hh; y++) {
    for (let x = 0; x < hw; x++) field[y * hw + x] = hash2(x + seed * 131, y * 1.7 + seed) - 0.5;
  }
  for (let y = 0; y < src.h; y++) {
    const fy = y * 0.5;
    const y0 = fy | 0;
    const ty = fy - y0;
    const rowA = y0 * hw;
    const rowB = Math.min(hh - 1, y0 + 1) * hw;
    for (let x = 0; x < src.w; x++) {
      const fx = x * 0.5;
      const x0 = fx | 0;
      const tx = fx - x0;
      const x1 = Math.min(hw - 1, x0 + 1);
      const a = field[rowA + x0] + (field[rowA + x1] - field[rowA + x0]) * tx;
      const b = field[rowB + x0] + (field[rowB + x1] - field[rowB + x0]) * tx;
      const k = (a + (b - a) * ty) * amount;
      const i = (y * src.w + x) * 3;
      d[i] += k;
      d[i + 1] += k;
      d[i + 2] += k;
    }
  }
}

export function fade(src: Frame, k: number): void {
  const d = src.data;
  for (let i = 0; i < d.length; i++) d[i] *= k;
}

/** Bilinear upscale of a small frame back to full resolution. */
export function upsample(src: Frame, w: number, h: number): Frame {
  const dst = new Frame(w, h);
  const sx = src.w / w;
  const sy = src.h / h;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const o = (y * w + x) * 3;
      for (let c = 0; c < 3; c++) dst.data[o + c] = sampleBilinear(src, x * sx, y * sy, c);
    }
  }
  return dst;
}

/**
 * Anamorphic streak: threshold hard, then smear only horizontally.
 * Kept deliberately weak — it should read as lens flare, not as fog.
 */
export function streak(src: Frame, intensity: number, tint: RGB = [0.55, 0.85, 1]): void {
  if (intensity <= 1e-3) return;
  const small = downsample(src, 4);
  const bright = brightPass(small, 0.75, 0.5);
  const R = 26;
  const stretched = new Frame(bright.w, bright.h);
  for (let y = 0; y < bright.h; y++) {
    const row = y * bright.w * 3;
    for (let c = 0; c < 3; c++) {
      let sum = 0;
      for (let k = -R; k <= R; k++) sum += bright.data[row + clamp(k, 0, bright.w - 1) * 3 + c];
      const norm = 1 / (2 * R + 1);
      for (let x = 0; x < bright.w; x++) {
        stretched.data[row + x * 3 + c] = sum * norm;
        sum +=
          bright.data[row + clamp(x + R + 1, 0, bright.w - 1) * 3 + c] -
          bright.data[row + clamp(x - R, 0, bright.w - 1) * 3 + c];
      }
    }
  }
  // gentle vertical diffusion so the smear has soft edges
  const soft = blur(stretched, 2, 2);
  const up = upsample(soft, src.w, src.h);
  for (let i = 0; i < src.data.length; i += 3) {
    src.data[i] += up.data[i] * intensity * tint[0] * 0.20;
    src.data[i + 1] += up.data[i + 1] * intensity * tint[1] * 0.20;
    src.data[i + 2] += up.data[i + 2] * intensity * tint[2] * 0.20;
  }
}

export const lerpRGB = (a: RGB, b: RGB, t: number): RGB => [
  lerp(a[0], b[0], t),
  lerp(a[1], b[1], t),
  lerp(a[2], b[2], t),
];
