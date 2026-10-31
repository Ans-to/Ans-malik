"""
Voice-over for the film, generated with Kokoro (open source, Apache-2.0, 82M params, ONNX).

    python blender-film/vo.py --out blender-film/out/vo.wav \
        --model /tmp/kokoro/kokoro-v1.0.onnx --voices /tmp/kokoro/voices-v1.0.bin

Each line is synthesised separately and placed on its planned frame, instead of reading the whole
script in one pass and hoping it lands on 15 seconds. That also gives the mix real per-line timing
to duck the music under, and gives the gates something to measure.

Kokoro's English phonemiser needs espeak-ng data; the `espeakng-loader` wheel ships it, so no
system package is installed for this.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import film_config as FC

OUT_SR = 48000


def trim_silence(x, sr, thresh=0.008, pad_ms=25):
    idx = np.where(np.abs(x) > thresh * np.max(np.abs(x) + 1e-9))[0]
    if len(idx) == 0:
        return x
    pad = int(sr * pad_ms / 1000)
    a = max(0, idx[0] - pad)
    b = min(len(x), idx[-1] + pad)
    return x[a:b]


def resample(x, src_sr, dst_sr):
    if src_sr == dst_sr:
        return x
    n = int(round(len(x) * dst_sr / float(src_sr)))
    src = np.linspace(0.0, 1.0, len(x), endpoint=False)
    dst = np.linspace(0.0, 1.0, n, endpoint=False)
    return np.interp(dst, src, x).astype(np.float32)


def fade(x, sr, ms=6):
    n = min(int(sr * ms / 1000), len(x) // 2)
    if n <= 0:
        return x
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="blender-film/out/vo.wav")
    ap.add_argument("--model", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--voice", default=FC.VO_VOICE)
    ap.add_argument("--speed", type=float, default=FC.VO_SPEED)
    args = ap.parse_args()

    from kokoro_onnx import Kokoro

    kokoro = Kokoro(args.model, args.voices)

    total = int(FC.DURATION * OUT_SR)
    track = np.zeros(total, dtype=np.float32)
    report = []

    for line in FC.VO_LINES:
        samples, sr = kokoro.create(line["text"], voice=args.voice, speed=args.speed,
                                    lang="en-us")
        x = np.asarray(samples, dtype=np.float32)
        if x.ndim > 1:
            x = x.mean(axis=1)
        x = trim_silence(x, sr)
        x = fade(resample(x, sr, OUT_SR), OUT_SR)

        peak = float(np.max(np.abs(x)) + 1e-9)
        x = x * (0.70 / peak)                       # consistent level line to line

        start = int(line["start"] / FC.FPS * OUT_SR)
        end = start + len(x)
        if end > total:
            print(f"[vo] WARNING {line['id']} overruns the film by "
                  f"{(end - total) / OUT_SR:.2f}s", file=sys.stderr)
            x = x[:max(0, total - start)]
            end = total
        track[start:end] += x

        report.append(dict(
            id=line["id"],
            text=line["text"],
            start_frame=line["start"],
            start_s=round(line["start"] / FC.FPS, 3),
            duration_s=round(len(x) / OUT_SR, 3),
            end_s=round(end / OUT_SR, 3),
        ))
        print(f"[vo] {line['id']}: {len(x) / OUT_SR:5.2f}s at {line['start'] / FC.FPS:5.2f}s "
              f"({len(x)} samples)")

    # never clip the sum of overlapping lines
    peak = float(np.max(np.abs(track)) + 1e-9)
    if peak > 0.95:
        track *= 0.95 / peak

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_wav(args.out, track, OUT_SR)

    meta = dict(voice=args.voice, speed=args.speed, sample_rate=OUT_SR, lines=report,
                total_s=round(len(track) / OUT_SR, 3))
    with open(os.path.splitext(args.out)[0] + "_times.json", "w") as fh:
        json.dump(meta, fh, indent=2)
    print(f"[vo] wrote {args.out} ({len(track) / OUT_SR:.2f}s)")


def write_wav(path, x, sr):
    """Minimal 16-bit PCM writer so the audio step needs no soundfile/scipy."""
    import struct

    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767.0).astype("<i2").tobytes()
    n = len(x)
    with open(path, "wb") as fh:
        fh.write(b"RIFF")
        fh.write(struct.pack("<I", 36 + len(pcm)))
        fh.write(b"WAVEfmt ")
        fh.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
        fh.write(b"data")
        fh.write(struct.pack("<I", len(pcm)))
        fh.write(pcm)
    return n


if __name__ == "__main__":
    main()
