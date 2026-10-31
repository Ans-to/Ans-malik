"""
Music bed for the film, synthesised from scratch — no samples, no library, no licence question.

    python blender-film/score.py --vo blender-film/out/vo.wav --out blender-film/out/score.wav

Everything is generated on the same 120 BPM grid the picture is cut to: a bar is 2 s, a beat is
0.5 s, each shot gets its own chord, and the impacts land exactly on the cuts. The bed ducks under
the voice-over using the voice's own envelope, so nothing is hand-automated per line.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import film_config as FC

SR = 48000

# one chord per shot, as (root_hz, [ratios])
CHORDS = {
    "A": [("A2", 110.00), ("C4", 261.63), ("E4", 329.63), ("B4", 493.88)],      # Am add9
    "B": [("F2", 87.31), ("A3", 220.00), ("C4", 261.63), ("E4", 329.63)],       # Fmaj7
    "C": [("C3", 130.81), ("E3", 164.81), ("G3", 196.00), ("D4", 293.66)],      # Cmaj9
    "D": [("G2", 98.00), ("B2", 123.47), ("D3", 146.83), ("G3", 196.00)],       # G
    "E": [("A2", 110.00), ("C4", 261.63), ("E4", 329.63), ("A4", 440.00)],      # Am
}


def fit(x, n):
    """Trim or zero-pad to exactly n samples."""
    if len(x) == n:
        return x
    if len(x) > n:
        return x[:n]
    return np.pad(x, (0, n - len(x)))


def frames_to_samples(f):
    return int(round(f / float(FC.FPS) * SR))


def env_adsr(n, sr, attack, release, total):
    e = np.ones(n, dtype=np.float32)
    a = min(int(attack * sr), n)
    r = min(int(release * sr), n)
    if a > 0:
        e[:a] = np.linspace(0.0, 1.0, a) ** 1.5
    if r > 0:
        e[-r:] *= np.linspace(1.0, 0.0, r) ** 1.2
    return e


def fft_shape(x, sr, lo=None, hi=None):
    """Smooth spectral low/high shelf — avoids needing scipy for a one-pole filter."""
    n = len(x)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    gain = np.ones_like(freqs)
    if hi is not None:
        gain *= 1.0 / (1.0 + (freqs / hi) ** 2)
    if lo is not None:
        gain *= (freqs / lo) ** 2 / (1.0 + (freqs / lo) ** 2)
    return np.fft.irfft(spec * gain, n).astype(np.float32)


def pad_voice(freq, dur, sr, phase=0.0):
    """Additive pad voice. No detuned pairs: two copies of the same partial drift into antiphase
    and punch a hole in the bed. Vibrato per partial gives the movement without the cancellation."""
    n = int(dur * sr)
    t = np.arange(n, dtype=np.float32) / sr
    out = np.zeros(n, dtype=np.float32)
    for mult, amp in ((1.0, 1.0), (2.0, 0.24), (3.0, 0.09), (4.0, 0.04)):
        vib = 0.32 * np.sin(2 * np.pi * 0.11 * mult * t + phase * 1.3)
        out += amp * np.sin(2 * np.pi * freq * mult * (1.0 + 0.0011 * mult) * t
                           + phase * mult + vib)
    lfo = 0.88 + 0.12 * np.sin(2 * np.pi * 0.07 * t + phase)
    return (out * lfo * 0.40).astype(np.float32)


def noise_burst(dur, sr, seed):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(int(dur * sr)).astype(np.float32)


def reverb(x, sr, decay=0.55, seed=3):
    rng = np.random.default_rng(seed)
    n = int(decay * sr)
    ir = rng.standard_normal(n).astype(np.float32) * np.exp(-np.linspace(0, 6.5, n))
    ir = fft_shape(ir, sr, lo=180.0, hi=6500.0)
    ir /= np.max(np.abs(ir)) + 1e-9
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    return (0.82 * x + 0.34 * wet.astype(np.float32))


def build_bed(total):
    bed_l = np.zeros(total, dtype=np.float32)
    bed_r = np.zeros(total, dtype=np.float32)

    # ---- sustained pad, one chord per shot, overlapping the cut by 0.25 s each side
    for shot in FC.SHOTS:
        s0 = max(0, frames_to_samples(shot["start"]) - int(0.12 * SR))
        s1 = min(total, frames_to_samples(shot["end"]) + int(0.22 * SR))
        dur = (s1 - s0) / float(SR)
        chunk_l = np.zeros(s1 - s0, dtype=np.float32)
        chunk_r = np.zeros(s1 - s0, dtype=np.float32)
        for i, (_, freq) in enumerate(CHORDS[shot["key"]]):
            v = pad_voice(freq, dur, SR, phase=i * 1.7)
            v = env_adsr(len(v), SR, 0.38, 0.55, dur)
            pan = 0.5 + 0.32 * np.sin(i * 2.1 + 0.7)
            chunk_l += v * np.sqrt(1.0 - pan) * 0.85
            chunk_r += v * np.sqrt(pan) * 0.85
        want = s1 - s0
        n = want
        tt = np.arange(n, dtype=np.float32) / SR
        sub = np.sin(2 * np.pi * CHORDS[shot["key"]][0][1] / 2.0 * tt) * env_adsr(
            n, SR, 0.30, 0.50, n / SR) * 0.052
        chunk_l += sub
        chunk_r += sub
        bed_l[s0:s1] += fit(chunk_l, want)
        bed_r[s0:s1] += fit(chunk_r, want)

    bed_l = fft_shape(bed_l, SR, lo=70.0, hi=4200.0)
    bed_r = fft_shape(bed_r, SR, lo=70.0, hi=4200.0)

    # ---- sub pulse on every bar (2 s at 120 BPM)
    for bar in range(int(FC.DURATION / 2.0) + 1):
        s0 = frames_to_samples(bar * 2 * FC.FPS)
        if s0 >= total:
            break
        n = min(int(0.75 * SR), total - s0)
        t = np.arange(n, dtype=np.float32) / SR
        pulse = np.sin(2 * np.pi * 55.0 * t) * np.exp(-t * 6.0) * 0.115
        click = np.sin(2 * np.pi * 110.0 * t) * np.exp(-t * 40.0) * 0.10
        bed_l[s0:s0 + n] += (pulse + click)
        bed_r[s0:s0 + n] += (pulse + click)

    # ---- ticks on every beat, from the second bar on, alternating pan
    for beat in range(int(FC.DURATION / 0.5) + 1):
        s0 = frames_to_samples(beat * FC.BEAT)
        if s0 >= total or beat < 2:
            continue
        n = min(int(0.05 * SR), total - s0)
        tick = noise_burst(0.05, SR, seed=beat)[:n] * np.exp(-np.arange(n) / (0.008 * SR)) * 0.030
        tick = fft_shape(tick, SR, lo=5200.0)
        pan = 0.30 if beat % 2 else 0.62
        bed_l[s0:s0 + n] += tick * (1.0 - pan)
        bed_r[s0:s0 + n] += tick * pan

    # ---- riser into every cut, and an impact on it
    for shot in FC.SHOTS[1:]:
        cut = frames_to_samples(shot["start"])
        n = int(0.85 * SR)
        s0 = max(0, cut - n)
        m = cut - s0
        t = np.linspace(0.0, 1.0, m, dtype=np.float32)
        hiss = noise_burst(m / SR + 0.01, SR, seed=shot["start"])[:m]
        hiss = fft_shape(hiss, SR, lo=900.0, hi=9000.0) * 0.075
        sweep_hz = 220.0 * (1.0 + 5.5 * t ** 1.6)
        tone = np.sin(2 * np.pi * np.cumsum(sweep_hz) / SR) * 0.030
        riser = (hiss + tone) * (t ** 2.2)
        bed_l[s0:cut] += riser
        bed_r[s0:cut] += riser

        imp_n = min(int(0.55 * SR), total - cut)
        if imp_n > 0:
            tt = np.arange(imp_n, dtype=np.float32) / SR
            sweep = 92.0 * np.exp(-tt * 5.5) + 38.0
            impact = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.exp(-tt * 7.0) * 0.42
            tail = fft_shape(noise_burst(imp_n / SR + 0.01, SR, seed=shot["start"] + 7)[:imp_n],
                             SR, lo=200.0, hi=900.0) * np.exp(-tt * 12.0) * 0.08
            bed_l[cut:cut + imp_n] += impact + tail
            bed_r[cut:cut + imp_n] += impact + tail

    bed_l = reverb(bed_l, SR, seed=5)
    bed_r = reverb(bed_r, SR, seed=9)
    return bed_l, bed_r


def duck_envelope(vo_mono, total, sr):
    """1.0 when the voice is silent, ~0.45 under it.

    Computed on a 240 Hz envelope, not per sample: the same shape for a fraction of the work.
    The release is symmetric, which gives a little pre-duck before each line — musically that is
    what you want anyway.
    """
    if vo_mono is None:
        return np.ones(total, dtype=np.float32)
    ds = SR // 240
    pad = (-len(vo_mono)) % ds
    mag = np.abs(np.pad(vo_mono, (0, pad))).reshape(-1, ds).max(axis=1)
    gate = (mag > 0.015).astype(np.float32)
    k = max(3, int(0.20 * 240))
    kernel = np.ones(k, dtype=np.float32) / k
    smooth = np.convolve(gate, kernel, mode="same")
    env_ds = 1.0 - 0.55 * np.clip(smooth * 1.8, 0.0, 1.0)
    env = np.interp(np.arange(total), np.arange(len(env_ds)) * ds, env_ds)
    return env.astype(np.float32)


def read_wav_mono(path):
    import wave

    with wave.open(path, "rb") as w:
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x


def write_wav_stereo(path, left, right, sr):
    import struct

    n = min(len(left), len(right))
    inter = np.empty(n * 2, dtype="<i2")
    inter[0::2] = (np.clip(left[:n], -1, 1) * 32767).astype("<i2")
    inter[1::2] = (np.clip(right[:n], -1, 1) * 32767).astype("<i2")
    pcm = inter.tobytes()
    with open(path, "wb") as fh:
        fh.write(b"RIFF")
        fh.write(struct.pack("<I", 36 + len(pcm)))
        fh.write(b"WAVEfmt ")
        fh.write(struct.pack("<IHHIIHH", 16, 1, 2, sr, sr * 4, 4, 16))
        fh.write(b"data")
        fh.write(struct.pack("<I", len(pcm)))
        fh.write(pcm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vo", default="blender-film/out/vo.wav")
    ap.add_argument("--out", default="blender-film/out/score.wav")
    ap.add_argument("--bed", type=float, default=0.62)
    args = ap.parse_args()

    total = int(FC.DURATION * SR)
    bed_l, bed_r = build_bed(total)

    vo = None
    if os.path.exists(args.vo):
        vo = read_wav_mono(args.vo)
        if len(vo) < total:
            vo = np.pad(vo, (0, total - len(vo)))
        vo = vo[:total]
    else:
        print(f"[score] no voice-over at {args.vo}; mixing bed only", file=sys.stderr)

    duck = duck_envelope(vo, total, SR)

    # bed level: measure RMS, then normalise so the mix is predictable run to run
    rms = float(np.sqrt(np.mean((bed_l ** 2 + bed_r ** 2) / 2.0)) + 1e-9)
    bed_gain = args.bed * (0.095 / rms)

    mix_l = bed_l * duck * bed_gain
    mix_r = bed_r * duck * bed_gain
    if vo is not None:
        mix_l = mix_l + vo
        mix_r = mix_r + vo

    # master: gentle soft clip rather than a limiter with lookahead
    peak = float(max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r))) + 1e-9)
    if peak > 0.89:
        mix_l = np.tanh(mix_l * (1.35 / peak)) * 0.89
        mix_r = np.tanh(mix_r * (1.35 / peak)) * 0.89

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_wav_stereo(args.out, mix_l, mix_r, SR)

    stats = dict(
        sample_rate=SR,
        duration_s=round(total / SR, 3),
        bed_gain=round(bed_gain, 5),
        duck_min=round(float(np.min(duck)), 3),
        ducked_fraction=round(float(np.mean(duck < 0.9)), 3),
        vo_peak=round(float(np.max(np.abs(vo))) if vo is not None else 0.0, 3),
        mix_peak=round(float(max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)))), 3),
        mix_rms=round(float(np.sqrt(np.mean((mix_l ** 2 + mix_r ** 2) / 2))), 4),
    )
    with open(os.path.splitext(args.out)[0] + "_stats.json", "w") as fh:
        json.dump(stats, fh, indent=2)
    print("[score] " + json.dumps(stats))


if __name__ == "__main__":
    main()
