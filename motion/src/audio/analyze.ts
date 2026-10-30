/**
 * analyze.ts — real signal analysis of the soundtrack.
 *
 * Nothing here is hard-coded from the synth score: the file is decoded, split
 * into bands, onset-detected, tempo-estimated and only then handed to the
 * renderer. Swap in your own WAV and the picture re-times itself.
 */

import { readFileSync } from 'node:fs';

export interface Hit {
  t: number;
  strength: number;
}

export interface Analysis {
  sampleRate: number;
  duration: number;
  bpm: number;
  /** seconds per beat */
  beat: number;
  /** detected kick/beat positions in seconds */
  beats: Hit[];
  onsets: Hit[];
  hop: number;
  /** per-frame normalised band energies (0..1) */
  low: Float32Array;
  mid: Float32Array;
  high: Float32Array;
  rms: Float32Array;
  /** energy of the low band at time t */
  lowAt(t: number): number;
  highAt(t: number): number;
  rmsAt(t: number): number;
  /** sum of exponential decays from kicks before t — 0..~1.5 punch value */
  punch(t: number, decay?: number): number;
  /** index of the last beat before t (-1 if none) */
  beatIndex(t: number): number;
  /** normalised position inside the current beat (0..1) */
  beatPhase(t: number): number;
}

function decodeWav(path: string): { left: Float32Array; right: Float32Array; sampleRate: number } {
  const buf = readFileSync(path);
  if (buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error('not a RIFF/WAVE file');
  }
  let pos = 12;
  let fmt: { channels: number; sampleRate: number; bits: number } | null = null;
  let dataStart = -1;
  let dataLen = 0;
  while (pos + 8 <= buf.length) {
    const id = buf.toString('ascii', pos, pos + 4);
    const size = buf.readUInt32LE(pos + 4);
    const body = pos + 8;
    if (id === 'fmt ') {
      fmt = {
        channels: buf.readUInt16LE(body + 2),
        sampleRate: buf.readUInt32LE(body + 4),
        bits: buf.readUInt16LE(body + 14),
      };
    } else if (id === 'data') {
      dataStart = body;
      dataLen = Math.min(size, buf.length - body);
    }
    pos = body + size + (size % 2);
  }
  if (!fmt || dataStart < 0) throw new Error('malformed wav');

  const bytes = fmt.bits / 8;
  const frames = Math.floor(dataLen / (bytes * fmt.channels));
  const left = new Float32Array(frames);
  const right = new Float32Array(frames);
  for (let i = 0; i < frames; i++) {
    const base = dataStart + i * bytes * fmt.channels;
    const l = bytes === 2 ? buf.readInt16LE(base) / 32768 : buf.readUInt8(base) / 128 - 1;
    const r =
      fmt.channels > 1
        ? bytes === 2
          ? buf.readInt16LE(base + bytes) / 32768
          : buf.readUInt8(base + bytes) / 128 - 1
        : l;
    left[i] = l;
    right[i] = r;
  }
  return { left, right, sampleRate: fmt.sampleRate };
}

const normArr = (a: Float32Array): Float32Array => {
  let max = 0;
  for (let i = 0; i < a.length; i++) max = Math.max(max, a[i]);
  if (max > 0) for (let i = 0; i < a.length; i++) a[i] /= max;
  return a;
};

export function analyzeAudio(path: string): Analysis {
  const { left, right, sampleRate } = decodeWav(path);
  const mono = new Float32Array(left.length);
  for (let i = 0; i < left.length; i++) mono[i] = (left[i] + right[i]) * 0.5;

  const hop = 256;
  const frameSize = 1024;
  const frames = Math.floor((mono.length - frameSize) / hop) + 1;

  // One-pole filters approximating a 3-band split.
  const lowLP = 0.02; // ~140 Hz at 44.1k
  const highHP = 0.45; // ~3.5 kHz
  const low = new Float32Array(frames);
  const mid = new Float32Array(frames);
  const high = new Float32Array(frames);
  const rms = new Float32Array(frames);

  let lpState = 0;
  let highPrev = 0;
  let highLP = 0;

  for (let f = 0; f < frames; f++) {
    const start = f * hop;
    let eLow = 0;
    let eMid = 0;
    let eHigh = 0;
    let eAll = 0;
    for (let i = 0; i < frameSize; i++) {
      const s = mono[start + i];
      lpState += (s - lpState) * lowLP;
      const lowS = lpState;
      highPrev = s - highPrev * 0.0; // placeholder to keep arithmetic explicit
      const hp = s - highLP;
      highLP += (s - highLP) * 0.08;
      eLow += lowS * lowS;
      eHigh += hp * hp;
      eMid += (s - lowS) * (s - lowS);
      eAll += s * s;
    }
    low[f] = eLow / frameSize;
    mid[f] = eMid / frameSize;
    high[f] = eHigh / frameSize;
    rms[f] = Math.sqrt(eAll / frameSize);
  }

  // log compression + positive flux
  const fluxOf = (arr: Float32Array): Float32Array => {
    const out = new Float32Array(arr.length);
    let prev = Math.log(1e-8 + arr[0]);
    for (let i = 1; i < arr.length; i++) {
      const cur = Math.log(1e-8 + arr[i]);
      out[i] = Math.max(0, cur - prev);
      prev = cur;
    }
    return out;
  };
  const fluxLow = fluxOf(low);
  const fluxHigh = fluxOf(high);
  const fluxAll = fluxOf(rms);

  const frameSec = hop / sampleRate;
  const peakPick = (arr: Float32Array, minGapFrames: number, sensitivity = 1.6): Hit[] => {
    const hits: Hit[] = [];
    const W = 24;
    let last = -1e9;
    for (let i = 1; i < arr.length; i++) {
      let mean = 0;
      let count = 0;
      for (let k = Math.max(0, i - W); k <= Math.min(arr.length - 1, i + W); k++) {
        mean += arr[k];
        count++;
      }
      mean /= count;
      const thresh = mean * sensitivity + 1e-6;
      if (arr[i] > thresh && arr[i] >= arr[i - 1] && (i + 1 >= arr.length || arr[i] >= arr[i + 1])) {
        if (i - last >= minGapFrames) {
          hits.push({ t: i * frameSec, strength: arr[i] });
          last = i;
        }
      }
    }
    return hits;
  };

  const onsets = peakPick(fluxAll, 3, 1.35);
  const kickRaw = peakPick(fluxLow, 8, 1.5);

  /* ------------------------------------------------------------ tempo map */
  // Autocorrelation of the full-band flux over plausible beat periods.
  const minBpm = 70;
  const maxBpm = 180;
  const lagMin = Math.round(60 / maxBpm / frameSec);
  const lagMax = Math.round(60 / minBpm / frameSec);
  let bestLag = lagMin;
  let bestScore = -1;
  const total = fluxAll.length;
  for (let lag = lagMin; lag <= lagMax; lag++) {
    let s = 0;
    for (let i = 0; i + lag < total; i++) s += fluxAll[i] * fluxAll[i + lag];
    // bias towards the middle of the range so 1/2 and 2x tempo don't win
    const bpm = 60 / (lag * frameSec);
    const bias = Math.exp(-Math.pow(Math.log2(bpm / 120) / 0.45, 2));
    const score = s * bias;
    if (score > bestScore) {
      bestScore = score;
      bestLag = lag;
    }
  }
  const bpm = Math.round((60 / (bestLag * frameSec)) * 10) / 10;
  const beat = 60 / bpm;

  // Snap detected low-band onsets onto the tempo grid: keep the best phase.
  let bestPhase = 0;
  let bestPhaseScore = -Infinity;
  for (let p = 0; p < 32; p++) {
    const phase = (p / 32) * beat;
    let sc = 0;
    for (const h of kickRaw) {
      const off = Math.abs(((h.t - phase + beat * 100) % beat + beat) % beat);
      const d = Math.min(off, beat - off);
      sc += Math.exp(-d * 40) * h.strength;
    }
    if (sc > bestPhaseScore) {
      bestPhaseScore = sc;
      bestPhase = phase;
    }
  }

  const duration = mono.length / sampleRate;
  const beats: Hit[] = [];
  // Extend the grid backwards so the first downbeat (t=0) is included even
  // though onset detection cannot fire on the very first frame.
  for (let k = Math.ceil(bestPhase / beat); k > 0; k--) {
    const t = bestPhase - k * beat;
    if (t < -beat * 0.5) break;
    if (t >= -beat * 0.06) beats.push({ t: Math.max(0, t), strength: 0.7 });
  }
  for (let k = 0; bestPhase + k * beat < duration; k++) {
    const t = bestPhase + k * beat;
    const near = kickRaw.find((h) => Math.abs(h.t - t) < beat * 0.25);
    beats.push({ t, strength: near ? Math.min(1, near.strength * 8) : 0.55 });
  }

  normArr(low);
  normArr(mid);
  normArr(high);
  normArr(rms);

  const sampleAt = (arr: Float32Array, t: number): number => {
    const i = Math.max(0, Math.min(arr.length - 1, Math.round(t / frameSec)));
    return arr[i];
  };

  const analysis: Analysis = {
    sampleRate,
    duration,
    bpm,
    beat,
    beats,
    onsets,
    hop,
    low,
    mid,
    high,
    rms,
    lowAt: (t) => sampleAt(low, t),
    highAt: (t) => sampleAt(high, t),
    rmsAt: (t) => sampleAt(rms, t),
    punch: (t, decay = 9) => {
      let v = 0;
      for (const b of beats) {
        if (b.t > t) break;
        if (t - b.t > 1.2) continue;
        v += Math.exp(-(t - b.t) * decay) * (0.7 + 0.3 * b.strength);
      }
      return v;
    },
    beatIndex: (t) => Math.floor((t - beats[0]?.t ?? 0) / beat),
    beatPhase: (t) => (((t - (beats[0]?.t ?? 0)) % beat) + beat) % beat / beat,
  };
  return analysis;
}
