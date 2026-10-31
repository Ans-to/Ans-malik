"""
Objective gates for the film. Every number below is measured from the delivered file, not asserted.

    python blender-film/gates.py --video out/silicon_preview.mp4 --audio out/score.wav \
        --manifest out/manifest_preview.json --json out/gates_preview.json

Nothing here trusts the renderer. A render can succeed, return no error, and still be black,
frozen, clipped, or silent. These checks read the actual pixels and samples:

    duration/resolution/fps   container is what was asked for
    black                     the fade in/out exists but did not eat the film
    motion                    frames change, and change differently over time
    cuts                      each planned cut is a real discontinuity, not a dissolve accident
    luma / saturation         the palette is dark-and-warm, not neon or washed out
    accent                    copper is present as an accent, in the shots that use it
    sharpness                 typography actually resolved: high-frequency energy spikes in type windows
    loudness / true peak      EBU R128 -16 LUFS, no inter-sample clipping
    voice                     speech is measurably above the bed in every VO window
    spectrum                  the score sits in the bands a film bed belongs in
    layout                    shots tile the timeline with no gap and no overlap
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import film_config as FC

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
AN_W, AN_H = 96, 54          # analysis resolution for the motion/luma pass


# --------------------------------------------------------------------------- ffmpeg plumbing
def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def probe(path):
    r = run([FFMPEG, "-hide_banner", "-i", path])
    err = r.stderr.decode("utf-8", "replace")
    info = {"duration": None, "width": None, "height": None, "fps": None,
            "codec": None, "pix_fmt": None, "streams": 0}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if m:
        h, mi, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mi) * 60 + float(s)
    for line in err.splitlines():
        if "Stream #" in line and "Video:" in line:
            info["streams"] += 1
            m = re.search(r"Video: (\w+)", line)
            if m:
                info["codec"] = m.group(1)
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                info["width"], info["height"] = int(m.group(1)), int(m.group(2))
            m = re.search(r"([\d.]+) fps", line)
            if m:
                info["fps"] = float(m.group(1))
            m = re.search(r"(yuv[\w]+|gbrp|rgb24)", line)
            if m:
                info["pix_fmt"] = m.group(1)
        elif "Stream #" in line and "Audio:" in line:
            info["streams"] += 1
            info["audio"] = True
    return info


def decode_video(path, fps=10, w=AN_W, h=AN_H):
    """Decode to small RGB frames -> float array (n, h, w, 3) in 0..1."""
    r = run([FFMPEG, "-v", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    n = len(buf) // (w * h * 3)
    return buf[:n * w * h * 3].reshape(n, h, w, 3).astype(np.float32) / 255.0


def decode_audio(path, sr=48000):
    """Decode to mono by averaging the channels in numpy, not with -ac 1.

    ffmpeg's stereo-to-mono matrix sums the channels with a 1/sqrt(2) coefficient each, so material
    that is identical in both channels comes out 3 dB hot: the delivered preview's 0.808-peak
    soundtrack decoded at 1.036 and tripped the clipping gate with 57 phantom samples. Averaging
    here keeps the decoded peak equal to the peak in the file.
    """
    r = run([FFMPEG, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"])
    a = np.frombuffer(r.stdout, dtype="<f4").astype(np.float32)
    if a.size % 2:
        a = a[:-1]
    return a.reshape(-1, 2).mean(axis=1).astype(np.float32)


def loudness(path):
    r = run([FFMPEG, "-hide_banner", "-i", path, "-af",
             "loudnorm=I=-16:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"])
    err = r.stderr.decode("utf-8", "replace")
    try:
        # take the JSON object that follows the loudnorm filter, and nothing after it
        m = re.search(r"\{\s*\"input_i\".*?\}", err, re.S)
        block = json.loads(m.group(0))
        return dict(lufs=float(block["input_i"]), tp=float(block["input_tp"]),
                    lra=float(block["input_lra"]), thresh=float(block["input_thresh"]))
    except Exception:
        return dict(lufs=None, tp=None, lra=None, thresh=None)


# --------------------------------------------------------------------------- metrics
def saturation(rgb):
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    return np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)


def hue_deg(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4))
    return h * 60.0


def edge_energy(gray):
    """Mean |Laplacian|: a cheap proxy for how much crisp detail is in the frame."""
    g = gray
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1])
    return float(np.abs(lap).mean())


def gate(name, value, ok, detail=""):
    return dict(gate=name, value=value, pass_=bool(ok), detail=detail)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    with open(args.manifest) as fh:
        man = json.load(fh)
    exp_w, exp_h = man["resolution"]
    shots = FC.SHOTS

    info = probe(args.video)
    frames = decode_video(args.video, fps=10)
    audio = decode_audio(args.audio)
    loud = loudness(args.audio)
    vo_times = None
    vo_path = os.path.join(os.path.dirname(args.audio), "vo_times.json")
    if os.path.exists(vo_path):
        with open(vo_path) as fh:
            vo_times = json.load(fh)

    results = []

    # ---- container
    results.append(gate("duration", round(info["duration"] or 0, 3),
                        abs((info["duration"] or 0) - FC.DURATION) <= 0.10,
                        f"target {FC.DURATION}s"))
    results.append(gate("resolution", f"{info['width']}x{info['height']}",
                        (info["width"], info["height"]) == (exp_w, exp_h),
                        f"target {exp_w}x{exp_h}"))
    results.append(gate("fps", info["fps"], (info["fps"] or 0) == FC.FPS, "target 30"))
    results.append(gate("codec", f"{info['codec']}/{info['pix_fmt']}",
                        info["pix_fmt"] in ("yuv420p", "yuvj420p"), "H.264 4:2:0 for playback"))

    # ---- luma / exposure
    lum = frames.mean(axis=(1, 2, 3))
    black = float(np.mean(lum < 0.012))
    results.append(gate("black_fraction", round(black, 4), black <= 0.12,
                        "fade in/out allowed, a black film is not"))
    mean_lum = float(lum.mean())
    results.append(gate("mean_luma", round(mean_lum, 4), 0.045 <= mean_lum <= 0.34,
                        "dark and moody, but not crushed"))
    results.append(gate("head_dark", round(float(lum[0]), 4), lum[0] < 0.05, "opens from black"))
    results.append(gate("tail_dark", round(float(lum[-1]), 4), lum[-1] < 0.06, "closes to black"))

    # ---- motion
    d = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2, 3))
    results.append(gate("motion_median", round(float(np.median(d)), 5), np.median(d) > 0.0015,
                        "the film is not a slideshow"))
    results.append(gate("motion_p95", round(float(np.percentile(d, 95)), 5),
                        np.percentile(d, 95) > 0.008, "moments of real movement exist"))
    frozen, run_len = 0, 0
    for v in d:
        run_len = run_len + 1 if v < 1e-5 else 0
        frozen = max(frozen, run_len)
    results.append(gate("frozen_run", frozen, frozen <= 6, "no dead stretches at 10 fps"))

    # ---- cuts land where they were planned, and are actual discontinuities
    cut_hits = []
    for shot in shots[1:]:
        cf = int(round((shot["start"] - 1) / float(FC.FPS) * 10))
        lo, hi = max(0, cf - 4), min(len(d), cf + 5)
        local = float(d[lo:hi].max()) if hi > lo else 0.0
        pct = float((d < local).mean()) if len(d) else 0.0
        cut_hits.append(dict(shot=shot["key"], frame10=cf, delta=round(local, 5),
                             percentile=round(pct, 3), pass_=pct >= 0.85))
    results.append(gate("cuts_detected", [c["percentile"] for c in cut_hits],
                        all(c["pass_"] for c in cut_hits),
                        "each cut is in the top 15% of frame deltas"))

    # ---- palette
    sat = saturation(frames)
    results.append(gate("mean_saturation", round(float(sat.mean()), 4), sat.mean() <= 0.45,
                        "premium restraint, not neon"))
    hue = hue_deg(frames)
    warm = ((hue > 8.0) & (hue < 46.0) & (sat > 0.22) & (frames.max(-1) > 0.10))
    results.append(gate("copper_presence", round(float(warm.mean()) * 100, 3),
                        float(warm.mean()) * 100 >= 0.15,
                        "% of pixels carrying the accent hue (target >= 0.15%)"))
    cool = ((hue > 190.0) & (hue < 250.0) & (sat > 0.22))
    results.append(gate("neon_blues", round(float(cool.mean()) * 100, 3),
                        float(cool.mean()) * 100 <= 1.5,
                        "the rejected look was neon-on-navy: keep it out"))

    # ---- typography resolved: hard edges inside each line's own box
    #
    # This used to rank whole-frame edge energy across the film, which conflates two unrelated
    # things: whether the words are sharp, and how busy the shot around them is. Shot D is a sparse
    # dark field of defocused slabs; its lettering measured 0.062 inside the word box -- sharper
    # than shot C's 0.043 -- while the frame-wide metric put it at the 48th percentile and failed it
    # three times. The manifest now carries each line's projected screen box, and the measurement is
    # the 99th percentile of the Laplacian inside that box, decoded at a fixed 480x270 so the
    # threshold means the same thing at preview and final resolution.
    TYPE_W, TYPE_H = 480, 270
    hi_res = decode_video(args.video, fps=10, w=TYPE_W, h=TYPE_H)
    type_hits = []
    for row in man.get("type", []):
        box = row.get("box")
        if not box:
            type_hits.append(dict(text=row["body"], edge=0.0, pass_=False,
                                  detail="no screen box in the manifest"))
            continue
        x0 = max(0, int(round(box[0] * TYPE_W)))
        y0 = max(0, int(round(box[1] * TYPE_H)))
        x1 = min(TYPE_W, int(round(box[2] * TYPE_W)))
        y1 = min(TYPE_H, int(round(box[3] * TYPE_H)))
        if x1 - x0 < 4 or y1 - y0 < 4:
            type_hits.append(dict(text=row["body"], edge=0.0, pass_=False,
                                  detail="box smaller than 4 px"))
            continue
        f10 = max(0, int(round((row["frame"] - 1) / float(FC.FPS) * 10)))
        best = 0.0
        for i in range(f10, min(len(hi_res), f10 + 12)):
            g = hi_res[i, y0:y1, x0:x1].mean(axis=-1)
            lap = np.abs(g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
                         - 4.0 * g[1:-1, 1:-1])
            best = max(best, float(np.percentile(lap, 99)))
        type_hits.append(dict(text=row["body"], edge=round(best, 3), pass_=best >= 0.15))
    results.append(gate("type_resolved", [t["edge"] for t in type_hits],
                        bool(type_hits) and all(t["pass_"] for t in type_hits),
                        "each line hard-edged inside its own box (p99 >= 0.15)"))

    # ---- audio
    results.append(gate("lufs", loud["lufs"], loud["lufs"] is not None
                        and abs(loud["lufs"] - (-16.0)) <= 2.0, "EBU R128 -16 +/- 2"))
    results.append(gate("true_peak", loud["tp"], loud["tp"] is not None and loud["tp"] <= -1.0,
                        "<= -1.0 dBTP"))
    results.append(gate("clipped_samples", int(np.sum(np.abs(audio) > 0.9999)),
                        int(np.sum(np.abs(audio) > 0.9999)) == 0, "no hard clipping"))
    results.append(gate("audio_length", round(len(audio) / 48000.0, 3),
                        abs(len(audio) / 48000.0 - FC.DURATION) <= 0.12, "matches picture"))

    if vo_times:
        sr = 48000
        voiced = np.zeros(len(audio), dtype=bool)
        for line in vo_times["lines"]:
            a = int(line["start_s"] * sr)
            b = int(min(line["end_s"], FC.DURATION) * sr)
            voiced[a:b] = True
        def rms(x):
            return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
        v = rms(audio[voiced]) if voiced.any() else 0.0
        nv = rms(audio[~voiced]) if (~voiced).any() else 1e-9
        ratio = 20.0 * np.log10(max(v, 1e-9) / max(nv, 1e-9))
        results.append(gate("voice_over_bed_db", round(float(ratio), 2), ratio >= 4.0,
                            "speech sits >= 4 dB above the bed"))

    # ---- spectral balance of the soundtrack
    spec = np.abs(np.fft.rfft(audio)) ** 2
    freqs = np.fft.rfftfreq(len(audio), 1 / 48000.0)
    tot = float(spec.sum()) + 1e-12
    bands = {}
    for lo, hi, name in ((20, 120, "sub"), (120, 600, "low"), (600, 2500, "mid"),
                         (2500, 9000, "top")):
        bands[name] = 100.0 * float(spec[(freqs >= lo) & (freqs < hi)].sum()) / tot
    results.append(gate("spectrum", {k: round(v, 1) for k, v in bands.items()},
                        10.0 <= bands["sub"] <= 42.0 and 30.0 <= bands["mid"] + bands["low"] <= 80.0,
                        "sub / low / mid / top split"))

    # ---- layout
    covered = sum(s["end"] - s["start"] + 1 for s in shots)
    contiguous = all(shots[i]["end"] + 1 == shots[i + 1]["start"] for i in range(len(shots) - 1))
    results.append(gate("timeline", f"{len(shots)} shots / {covered} frames",
                        contiguous and covered == FC.FRAMES and shots[0]["start"] == 1,
                        "shots tile 1..450 with no gap or overlap"))

    passed = all(r["pass_"] for r in results)
    report = dict(
        video=os.path.abspath(args.video),
        preset=man.get("preset"),
        passed=passed,
        passed_count=sum(1 for r in results if r["pass_"]),
        total=len(results),
        gates=results,
        probe=info,
        loudness=loud,
        cuts=cut_hits,
        type=type_hits,
    )

    for r in results:
        mark = "PASS" if r["pass_"] else "FAIL"
        print(f"[{mark}] {r['gate']:<18} {str(r['value'])[:70]:<70} {r['detail']}")
    print(f"\n{report['passed_count']}/{report['total']} gates passed")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=2, default=str)
        print("report ->", args.json)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
