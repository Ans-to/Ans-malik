/**
 * synth.ts — the soundtrack, also written in code.
 *
 * 120 BPM, four bars of 4/4. Kick / snare / hats / sub-bass / pad / riser /
 * impact, all synthesised sample-by-sample. No samples, no licensing, no
 * external audio files — and the tempo grid is exact, so the picture can lock
 * to it sample-accurately.
 */

import { writeFileSync } from 'node:fs';
import { clamp } from '../core/math.ts';

export interface Soundtrack {
  left: Float32Array;
  right: Float32Array;
  sampleRate: number;
  bpm: number;
  duration: number;
}

/** Deterministic white noise (xorshift) — identical render on every machine. */
function rng(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return (s / 0xffffffff) * 2 - 1;
  };
}

export function synthesizeSoundtrack(bpm = 120, bars = 4): Soundtrack {
  const sampleRate = 44100;
  const beat = 60 / bpm;
  const duration = bars * 4 * beat;
  const n = Math.ceil(duration * sampleRate) + sampleRate;

  const dry = new Float32Array(n);
  const sendL = new Float32Array(n); // reverb send
  const sendR = new Float32Array(n);
  const noise = rng(0x9e3779b9);

  const write = (i: number, v: number, pan = 0, send = 0): void => {
    if (i < 0 || i >= n) return;
    const l = pan <= 0 ? 1 : 1 - pan;
    const r = pan >= 0 ? 1 : 1 + pan;
    dry[i] += v * (0.5 + l * 0.5);
    if (send > 0) {
      sendL[i] += v * send * r;
      sendR[i] += v * send * l;
    }
  };

  /* ------------------------------------------------------------------ drums */
  const kick = (at: number, gain = 1): void => {
    const len = Math.floor(0.46 * sampleRate);
    let phase = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const f = 46 + 120 * Math.exp(-t * 32);
      phase += (2 * Math.PI * f) / sampleRate;
      const env = Math.exp(-t * 6.8);
      const click = Math.exp(-t * 240) * 0.5;
      const v = (Math.sin(phase) * env + click * (noise() * 0.6)) * 0.85 * gain;
      write(at + i, Math.tanh(v * 1.4) * 0.62, 0, 0.02);
    }
  };

  const snare = (at: number, gain = 1): void => {
    const len = Math.floor(0.3 * sampleRate);
    let hp = 0;
    let prev = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const nz = noise();
      hp = nz - prev * 0.7;
      prev = nz;
      const env = Math.exp(-t * 19);
      const body = Math.sin(2 * Math.PI * 186 * t) * Math.exp(-t * 27) * 0.34;
      const v = (hp * 0.55 + body) * env * 0.5 * gain;
      write(at + i, v, 0.12, 0.22);
    }
  };

  const hat = (at: number, gain = 1, open = false): void => {
    const len = Math.floor((open ? 0.22 : 0.055) * sampleRate);
    let prev = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const nz = noise();
      const hp = nz - prev;
      prev = nz;
      const env = Math.exp(-t * (open ? 13 : 62));
      write(at + i, hp * env * 0.12 * gain, -0.28, 0.05);
    }
  };

  const crash = (at: number, gain = 1): void => {
    const len = Math.floor(1.6 * sampleRate);
    let prev = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const nz = noise();
      const hp = nz - prev * 0.92;
      prev = nz;
      const env = Math.exp(-t * 2.6);
      write(at + i, hp * env * 0.16 * gain, 0.2, 0.5);
    }
  };

  /* ------------------------------------------------------------------ tonal */
  const bass = (at: number, freq: number, dur = 0.24, gain = 1): void => {
    const len = Math.floor(dur * sampleRate);
    let lp = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const env = Math.min(1, t * 260) * Math.exp(-t * 7.5);
      const s =
        Math.sin(2 * Math.PI * freq * t) +
        0.42 * Math.sin(2 * Math.PI * freq * 2 * t) +
        0.2 * Math.sin(2 * Math.PI * freq * 3 * t);
      lp += (s - lp) * 0.22;
      write(at + i, Math.tanh(lp * 1.1) * env * 0.3 * gain, 0, 0.04);
    }
  };

  const pad = (at: number, freqs: number[], dur: number, gain = 1): void => {
    const len = Math.floor(dur * sampleRate);
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const attack = clamp(t / 0.55);
      const release = clamp((dur - t) / 0.45);
      const env = Math.pow(Math.min(attack, release), 1.6);
      let s = 0;
      for (let k = 0; k < freqs.length; k++) {
        const f = freqs[k];
        const detune = 1 + (k % 2 === 0 ? 0.0016 : -0.0014);
        s += Math.sin(2 * Math.PI * f * detune * t + k) * 0.6;
        s += Math.sin(2 * Math.PI * f * 2.002 * t) * 0.12;
      }
      const trem = 0.86 + 0.14 * Math.sin(2 * Math.PI * 0.9 * t);
      write(at + i, (s / freqs.length) * env * trem * 0.16 * gain, 0, 0.55);
    }
  };

  const riser = (at: number, dur: number, gain = 1): void => {
    const len = Math.floor(dur * sampleRate);
    let phase = 0;
    let bp = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const k = t / dur;
      const f = 180 + 2400 * k * k;
      phase += (2 * Math.PI * f) / sampleRate;
      const nz = noise();
      bp += (nz - bp) * (0.02 + 0.16 * k);
      const env = Math.pow(k, 2.2);
      write(at + i, (bp * 0.5 + Math.sin(phase) * 0.15) * env * 0.34 * gain, 0.1 * k, 0.35);
    }
  };

  const impact = (at: number, gain = 1): void => {
    const len = Math.floor(1.4 * sampleRate);
    let phase = 0;
    let prev = 0;
    for (let i = 0; i < len; i++) {
      const t = i / sampleRate;
      const f = 32 + 70 * Math.exp(-t * 9);
      phase += (2 * Math.PI * f) / sampleRate;
      const nz = noise();
      const hp = nz - prev * 0.8;
      prev = nz;
      const env = Math.exp(-t * 3.4);
      const v = (Math.sin(phase) * 0.7 + hp * 0.35) * env * 0.6 * gain;
      write(at + i, Math.tanh(v * 1.6) * 0.7, 0, 0.35);
    }
  };

  /* -------------------------------------------------------------- arrangement */
  const B = (b: number): number => Math.floor(b * beat * sampleRate);

  const A1 = 55;
  const A2 = 110;
  const patterns = [0, 0, 3, 5]; // semitone offsets for the bass line
  const semis = (root: number, s: number): number => root * Math.pow(2, s / 12);

  // Pad bed (A minor 9)
  pad(B(0), [110, 164.81, 220, 261.63], 16 * beat + 0.6, 1);
  pad(B(8), [110, 164.81, 246.94, 293.66], 8 * beat, 0.85);

  for (let bar = 0; bar < bars; bar++) {
    for (let q = 0; q < 4; q++) {
      const b = bar * 4 + q;
      const at = B(b);

      if (b < 7 || b >= 8) kick(at, b === 12 ? 1.25 : 1);
      if (b === 7) kick(at, 0.6);

      // hats
      const openAt = bar === 2 ? 7 : -1;
      for (let e = 0; e < 2; e++) {
        const sub = at + Math.floor((e * beat) / 2 * sampleRate);
        if (bar >= 1 && e === 1) hat(sub, 0.7, openAt === b && e === 1);
        else hat(sub, 0.55, false);
      }
      if (bar === 3) {
        for (let s = 0; s < 4; s++) hat(at + Math.floor((s * beat) / 4 * sampleRate), 0.36, false);
      }

      // backbeat
      if (q % 2 === 1) snare(at, bar === 3 ? 1.05 : 0.9);
      if (bar === 2 && q === 3) snare(at + Math.floor((beat / 2) * sampleRate), 0.5);

      // bass
      const root = semis(A1, patterns[bar % 4]);
      bass(at, b === 12 ? A2 : root, 0.26, b >= 12 ? 1.1 : 0.95);
      if (b >= 12) bass(at + Math.floor((beat / 2) * sampleRate), semis(A2, 12), 0.18, 0.6);
      if (b < 8 && q === 2) bass(at + Math.floor((beat / 2) * sampleRate), semis(root, 12), 0.16, 0.5);
    }
  }

  riser(B(8), 4 * beat - 0.05, 0.9);
  riser(B(4) + Math.floor(beat * sampleRate * 2), 2 * beat, 0.35);
  impact(B(12), 1.15);
  crash(B(12), 1);
  crash(B(14), 0.5);

  /* --------------------------------------------------------------- reverb */
  // Schroeder-ish: 4 combs + 2 allpasses, applied to the send bus.
  const reverb = (input: Float32Array, spread: number): Float32Array => {
    const out = new Float32Array(input.length);
    const combs = [1687, 1601, 2053, 2251].map((d) => Math.floor(d * spread));
    const buf = combs.map((d) => new Float32Array(d));
    const idx = combs.map(() => 0);
    const damp = 0.28;
    const fb = 0.79;
    let lp = 0;
    for (let i = 0; i < input.length; i++) {
      let s = 0;
      for (let c = 0; c < combs.length; c++) {
        const b = buf[c];
        const j = idx[c];
        const y = b[j];
        s += y;
        lp = y * (1 - damp) + lp * damp;
        b[j] = input[i] + lp * fb;
        idx[c] = (j + 1) % b.length;
      }
      out[i] = s / combs.length;
    }
    // allpass diffusion
    for (const [d, g] of [[556, 0.5], [441, 0.5]] as Array<[number, number]>) {
      const b = new Float32Array(d);
      let p = 0;
      for (let i = 0; i < out.length; i++) {
        const v = out[i];
        const y = b[p];
        b[p] = v + y * g;
        out[i] = y - v * g;
        p = (p + 1) % d;
      }
    }
    return out;
  };

  const wetL = reverb(sendL, 1.0);
  const wetR = reverb(sendR, 1.13);

  const left = new Float32Array(n);
  const right = new Float32Array(n);
  let peak = 0;
  for (let i = 0; i < n; i++) {
    const fadeIn = Math.min(1, i / (sampleRate * 0.02));
    const fadeOut = Math.min(1, (n - i) / (sampleRate * 0.35));
    const f = fadeIn * fadeOut;
    const l = (dry[i] + wetL[i] * 0.5) * f;
    const r = (dry[i] + wetR[i] * 0.5) * f;
    left[i] = Math.tanh(l * 1.15) * 0.92;
    right[i] = Math.tanh(r * 1.15) * 0.92;
    peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
  }
  const norm = peak > 0 ? 0.89 / peak : 1;
  for (let i = 0; i < n; i++) {
    left[i] *= norm;
    right[i] *= norm;
  }

  const cut = Math.ceil(duration * sampleRate);
  return {
    left: left.subarray(0, cut),
    right: right.subarray(0, cut),
    sampleRate,
    bpm,
    duration,
  };
}

/** 16-bit PCM stereo WAV. */
export function writeWav(path: string, s: Soundtrack): void {
  const frames = s.left.length;
  const bytes = frames * 4;
  const buf = Buffer.alloc(44 + bytes);
  buf.write('RIFF', 0, 'ascii');
  buf.writeUInt32LE(36 + bytes, 4);
  buf.write('WAVE', 8, 'ascii');
  buf.write('fmt ', 12, 'ascii');
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); // PCM
  buf.writeUInt16LE(2, 22); // stereo
  buf.writeUInt32LE(s.sampleRate, 24);
  buf.writeUInt32LE(s.sampleRate * 4, 28);
  buf.writeUInt16LE(4, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36, 'ascii');
  buf.writeUInt32LE(bytes, 40);
  let o = 44;
  for (let i = 0; i < frames; i++) {
    buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(s.left[i] * 32767))), o);
    buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(s.right[i] * 32767))), o + 2);
    o += 4;
  }
  writeFileSync(path, buf);
}
