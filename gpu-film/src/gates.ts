/**
 * gates.ts — the four measurable gates from the spec, implemented for real.
 *
 * Part F calls for an OpenCLIP aesthetic gate. The weights live on
 * huggingface.co, which is network-blocked in this sandbox (see ENV_AUDIT.md),
 * so `aestheticGate()` is a documented proxy: it measures the same qualities
 * CLIP prompts would be standing in for — tonal range, local contrast, edge
 * energy, colour discipline, negative space — and is calibrated against the
 * passing reference frames in assets/. Every report prints `proxy: true` so
 * nobody mistakes it for the CLIP number. `npm run gate:clip` runs the real
 * thing on a machine with HF access.
 */

import { spawnSync } from 'node:child_process';
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { existsSync } from 'node:fs';

export interface GateResult {
  name: string;
  pass: boolean;
  metrics: Record<string, number>;
  thresholds: Record<string, number>;
  notes: string[];
}

const ff = (): string => {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const local = join(process.cwd(), 'tools/ffmpeg');
  if (existsSync(local)) return local;
  return 'ffmpeg';
};

/** Decode a file (image or video, optionally a frame range) to raw gray/rgb. */
export function rawFrames(
  path: string,
  w: number,
  h: number,
  opts: { fps?: number; ss?: number; frames?: number } = {},
): Buffer[] {
  const args = ['-v', 'error'];
  if (opts.ss !== undefined) args.push('-ss', String(opts.ss));
  args.push('-i', path);
  if (opts.fps) args.push('-vf', `scale=${w}:${h},fps=${opts.fps}`);
  else args.push('-vf', `scale=${w}:${h}`);
  if (opts.frames) args.push('-frames:v', String(opts.frames));
  args.push('-f', 'rawvideo', '-pix_fmt', 'rgb24', '-');
  const res = spawnSync(ff(), args, { maxBuffer: 1024 * 1024 * 1024 });
  if (res.status !== 0) throw new Error(`ffmpeg decode failed (${ff()}): ${res.stderr?.toString() ?? 'no stderr'}`);
  const buf = res.stdout as Buffer;
  const size = w * h * 3;
  const out: Buffer[] = [];
  for (let i = 0; i + size <= buf.length; i += size) out.push(buf.subarray(i, i + size));
  return out;
}

/* ------------------------------------------------ PART H step 9: slideshow */

/**
 * detect_slideshow: if the frame-to-frame difference is near zero for a long
 * stretch, the "animation" is a slideshow. Measured as the fraction of
 * consecutive-frame pairs below a motion floor, plus the longest static run.
 */
export function slideshowGate(path: string, fps = 30): GateResult {
  const w = 160;
  const h = 90;
  const frames = rawFrames(path, w, h, { fps });
  const diffs: number[] = [];
  for (let i = 1; i < frames.length; i++) {
    const A = frames[i - 1];
    const B = frames[i];
    let s = 0;
    for (let p = 0; p < A.length; p += 3) {
      s += Math.abs(A[p] - B[p]) + Math.abs(A[p + 1] - B[p + 1]) + Math.abs(A[p + 2] - B[p + 2]);
    }
    diffs.push(s / (w * h * 3 * 255));
  }
  diffs.sort((a, b) => a - b);
  const median = diffs[Math.floor(diffs.length / 2)] ?? 0;
  let run = 0;
  let longest = 0;
  for (const d of diffs) {
    if (d < 0.0008) {
      run++;
      longest = Math.max(longest, run);
    } else run = 0;
  }
  const staticFraction = diffs.filter((d) => d < 0.0008).length / Math.max(1, diffs.length);
  const thresholds = { maxStaticFraction: 0.18, maxStaticRunFrames: 24, minMedianMotion: 0.0015 };
  const pass = staticFraction <= thresholds.maxStaticFraction && longest <= thresholds.maxStaticRunFrames && median >= thresholds.minMedianMotion;
  return {
    name: 'slideshow (Part H step 9)',
    pass,
    metrics: { staticFraction, longestStaticRun: longest, medianFrameDelta: median, frames: diffs.length },
    thresholds,
    notes: pass ? [] : ['static stretches detected — animation is not carrying the frame'],
  };
}

/* --------------------------------- PART H step 20: freezedetect + scenes */

export function freezeGate(path: string): GateResult {
  const res = spawnSync(ff(), ['-v', 'info', '-i', path, '-vf', 'freezedetect=n=0.001:d=0.4', '-f', 'null', '-'], {
    encoding: 'utf8',
  });
  const out = `${res.stderr ?? ''}`;
  const hits = (out.match(/freeze_start/g) ?? []).length;
  const thresholds = { maxFreezes: 2 };
  return {
    name: 'freezedetect (Part H step 20)',
    pass: hits <= thresholds.maxFreezes,
    metrics: { freezes: hits },
    thresholds,
    notes: hits === 0 ? [] : [`${hits} frozen segment(s) >= 0.4 s`],
  };
}

/* ------------------------------------- Part H step 16: transition variety */

/**
 * transition_audit: counts distinct transition types actually present in the
 * timeline (read from the EDL the scene file exports) and verifies no single
 * type exceeds a share of the total. Uniqueness is enforced by construction:
 * helpers in transitions.ts register themselves as they are instantiated.
 */
export function transitionAudit(edl: Array<{ type: string }>): GateResult {
  const counts: Record<string, number> = {};
  for (const e of edl) counts[e.type] = (counts[e.type] ?? 0) + 1;
  const types = Object.keys(counts).length;
  const total = edl.length || 1;
  const maxShare = Math.max(...Object.values(counts).map((c) => c / total));
  const thresholds = { minTypes: 5, maxSingleShare: 0.45 };
  return {
    name: 'transition_audit (Part H step 16)',
    pass: types >= thresholds.minTypes && maxShare <= thresholds.maxSingleShare,
    metrics: { distinctTypes: types, totalTransitions: edl.length, maxSingleShare: Number(maxShare.toFixed(3)) },
    thresholds,
    notes: types < thresholds.minTypes ? [`only ${types} transition types; spec requires >= 5`] : [],
  };
}

/* ---------------------------------------------- Part F: aesthetic gate */

export interface AestheticScore {
  premium: number;
  slop: number;
  gap: number;
  pass: boolean;
}

/**
 * Proxy for the CLIP premium-vs-slop embedding comparison.
 * Same intent (does this frame read as premium motion design?) measured with
 * image statistics rather than text-image similarity — see file header.
 */
export function scoreFrame(path: string, ss?: number): AestheticScore {
  const w = 192;
  const h = 108;
  const [f] = rawFrames(path, w, h, ss !== undefined ? { ss, frames: 1 } : { frames: 1 });
  if (!f) return { premium: 0, slop: 0, gap: -1, pass: false };

  const lum = new Float32Array(w * h);
  let sum = 0;
  for (let p = 0, i = 0; p < w * h; p++, i += 3) {
    lum[p] = (f[i] * 0.299 + f[i + 1] * 0.587 + f[i + 2] * 0.114) / 255;
    sum += lum[p];
  }
  const mean = sum / (w * h);
  let variance = 0;
  for (let p = 0; p < w * h; p++) variance += (lum[p] - mean) ** 2;
  const std = Math.sqrt(variance / (w * h));

  // local contrast (Sobel magnitude mean) — detail without noise
  let edge = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const gx = lum[y * w + x + 1] - lum[y * w + x - 1];
      const gy = lum[(y + 1) * w + x] - lum[(y - 1) * w + x];
      edge += Math.hypot(gx, gy);
    }
  }
  edge /= (w - 2) * (h - 2);

  // negative space: share of pixels below 12% luminance (dark, restful areas)
  let dark = 0;
  for (let p = 0; p < w * h; p++) if (lum[p] < 0.12) dark++;
  const negativeSpace = dark / (w * h);

  // clipped highlights: premium grades rarely blow out large areas
  let blown = 0;
  for (let p = 0; p < w * h; p++) if (lum[p] > 0.985) blown++;

  // hue discipline: how much chroma is concentrated in few hues
  const hist = new Float32Array(12);
  for (let p = 0, i = 0; p < w * h; p++, i += 3) {
    const r = f[i] / 255, g = f[i + 1] / 255, b = f[i + 2] / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    const sat = mx === 0 ? 0 : (mx - mn) / mx;
    if (sat < 0.12 || mx < 0.08) continue;
    let hue = 0;
    if (mx === r) hue = ((g - b) / (mx - mn)) % 6;
    else if (mx === g) hue = (b - r) / (mx - mn) + 2;
    else hue = (r - g) / (mx - mn) + 4;
    hue = (hue * 60 + 360) % 360;
    hist[Math.floor(hue / 30)] += 1;
  }
  const hueTotal = hist.reduce((a, b) => a + b, 0) || 1;
  let entropy = 0;
  for (const v of hist) {
    const p = v / hueTotal;
    if (p > 0) entropy -= p * Math.log2(p);
  }
  // 3.58 bits = perfectly uniform hue spread (12 bins); disciplined grades sit low
  const hueEntropy = entropy / Math.log2(12);

  const premium = clamp01(
    0.30 * clamp01(std / 0.26) +
      0.26 * clamp01(edge / 0.055) +
      0.20 * clamp01(negativeSpace / 0.55) +
      0.12 * (1 - clamp01(blown / (w * h * 0.02))) +
      0.12 * (1 - clamp01(hueEntropy / 0.62)),
  );
  const slop = clamp01(
    0.4 * (1 - clamp01(std / 0.12)) + 0.3 * (1 - clamp01(edge / 0.02)) + 0.3 * clamp01(blown / (w * h * 0.05)),
  );
  const gap = premium - slop;
  return { premium, slop, gap, pass: gap > 0.08 };
}

const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);

export function scoreSequence(dir: string, step = 10): GateResult {
  const files = readdirSync(dir)
    .filter((f) => /\.(png|jpg)$/i.test(f))
    .sort()
    .filter((_, i) => i % step === 0);
  const scores = files.map((f) => scoreFrame(join(dir, f)));
  const avgGap = scores.reduce((a, s) => a + s.gap, 0) / Math.max(1, scores.length);
  const fails = scores.filter((s) => !s.pass).length;
  const thresholds = { minAvgGap: 0.08, maxFailShare: 0.2 };
  const failShare = fails / Math.max(1, scores.length);
  return {
    name: 'aesthetic gate (Part F, proxy)',
    pass: avgGap >= thresholds.minAvgGap && failShare <= thresholds.maxFailShare,
    metrics: {
      avgPremium: Number((scores.reduce((a, s) => a + s.premium, 0) / Math.max(1, scores.length)).toFixed(3)),
      avgSlop: Number((scores.reduce((a, s) => a + s.slop, 0) / Math.max(1, scores.length)).toFixed(3)),
      avgGap: Number(avgGap.toFixed(3)),
      framesScored: scores.length,
      failShare: Number(failShare.toFixed(3)),
      proxy: 1,
    },
    thresholds,
    notes: ['proxy: true — OpenCLIP weights unreachable in this sandbox (ENV_AUDIT.md)'],
  };
}

/** Loudness / peak gate used at step 18. */
export function audioGate(path: string): GateResult {
  const res = spawnSync(ff(), ['-v', 'info', '-i', path, '-af', 'volumedetect', '-f', 'null', '-'], { encoding: 'utf8' });
  const err = String(res.stderr ?? '');
  const mean = Number((err.match(/mean_volume:\s*(-?[\d.]+)/) ?? [])[1] ?? NaN);
  const max = Number((err.match(/max_volume:\s*(-?[\d.]+)/) ?? [])[1] ?? NaN);
  const thresholds = { minMean: -30, maxMean: -12, maxPeak: -0.5 };
  return {
    name: 'audio level (Part H step 18)',
    pass: mean > thresholds.minMean && mean < thresholds.maxMean && max < thresholds.maxPeak,
    metrics: { meandB: mean, maxdB: max },
    thresholds,
    notes: [],
  };
}
