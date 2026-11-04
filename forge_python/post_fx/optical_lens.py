"""Optical finishing for RGB frames and video chunks (requires ffmpeg/ffprobe)."""
import argparse
import subprocess
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe
import imageio_ffmpeg

import cv2
import numpy as np
from numba import njit, prange
from scipy.ndimage import gaussian_filter

@njit(parallel=True, fastmath=True)
def apply_bloom_vignette_and_grain(frame, bloom, grain_seed):
    """Fuse screen bloom, radial vignette and deterministic luminance grain.

    Inputs are float32 RGB arrays in [0, 1]. The hash-based grain is uniform
    with standard deviation approximately 0.025, shared by all channels.
    """
    h, w, _ = frame.shape
    out = np.empty_like(frame)
    cx, cy = (w - 1) * 0.5, (h - 1) * 0.5
    max_dist_sq = max(cx * cx + cy * cy, 1.0)
    for y in prange(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            vignette = 1.0 - 0.38 * (dx * dx + dy * dy) / max_dist_sq
            hash_val = ((x * 73856093) ^ (y * 19349663) ^ (grain_seed * 83492791)) & 0xFF
            grain = ((hash_val + 0.5) / 128.0 - 1.0) * (0.025 * 1.7320508075688772)
            for ch in range(3):
                base = frame[y, x, ch] * vignette
                glow = bloom[y, x, ch] * 0.35
                blended = 1.0 - (1.0 - base) * (1.0 - glow)
                out[y, x, ch] = min(1.0, max(0.0, blended + grain))
    return out


def _finish_with_seed(frame, grain_seed):
    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or not frame.shape[0] or not frame.shape[1]:
        raise ValueError('expected a nonempty H x W x 3 uint8 RGB frame')
    image = frame.astype(np.float32) / 255.0
    luminance = image @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    highlights = image * (luminance > 210 / 255.0)[..., None]
    h, w = frame.shape[:2]
    # A quarter-size Gaussian approximates an 18-pixel full-resolution blur.
    # Explicit dimensions also support very small frames.
    sw, sh = max(1, round(w / 4)), max(1, round(h / 4))
    small = cv2.resize(highlights, (sw, sh), interpolation=cv2.INTER_AREA)
    blurred = gaussian_filter(small, sigma=(18 * sh / h, 18 * sw / w, 0))
    bloom = cv2.resize(blurred, (w, h), interpolation=cv2.INTER_LINEAR)
    image = apply_bloom_vignette_and_grain(image, bloom, grain_seed)
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    dx = (xx - (w - 1) / 2) / max((w - 1) / 2, 1)
    dy = (yy - (h - 1) / 2) / max((h - 1) / 2, 1)
    radius = np.sqrt(dx * dx + dy * dy)
    strength = np.clip((radius - 0.8) / 0.2, 0, 1) * 1.5
    length = np.maximum(radius, 1e-6)
    ox, oy = strength * dx / length, strength * dy / length
    for channel, sign in ((0, 1), (2, -1)):
        image[:, :, channel] = cv2.remap(image[:, :, channel].copy(), xx + sign * ox, yy + sign * oy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return np.rint(image * 255).astype(np.uint8)


def finish_frame(frame, rng=None):
    """Finish an RGB uint8 frame; pass a seeded Generator for reproducibility."""
    rng = rng if rng is not None else np.random.default_rng()
    return _finish_with_seed(frame, int(rng.integers(0, 2**31)))


def process_frame_cinematic(frame_bgr, frame_idx):
    """OpenCV BGR adapter with deterministic per-frame grain."""
    if not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or not frame_bgr.shape[0] or not frame_bgr.shape[1]:
        raise ValueError('expected a nonempty H x W x 3 uint8 BGR frame')
    return cv2.cvtColor(_finish_with_seed(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), int(frame_idx) % (2**31)), cv2.COLOR_RGB2BGR)

def finish_video(source, destination, seed=0):
    """Decode every frame, finish it, then encode with audio copied from the source."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('input and output must be different files')
    reader = imageio_ffmpeg.read_frames(str(source), pix_fmt="rgb24")
    info = next(reader)
    reader.close()
    w, h = info['size']
    fps = str(info['fps'])
    if float(fps) <= 0: raise ValueError('video has no usable frame rate')
    decoder = subprocess.Popen([get_ffmpeg_exe(), '-v', 'error', '-i', str(source), '-map', '0:v:0', '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    encoder = subprocess.Popen([get_ffmpeg_exe(), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', fps, '-i', '-', '-i', str(source), '-map', '0:v:0', '-map', '1:a?', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(destination)], stdin=subprocess.PIPE)
    rng = np.random.default_rng(seed)
    try:
        while True:
            data = decoder.stdout.read(w * h * 3)
            if not data: break
            if len(data) != w * h * 3: raise RuntimeError('incomplete decoded frame')
            frame = np.frombuffer(data, np.uint8).reshape(h, w, 3)
            encoder.stdin.write(finish_frame(frame, rng).tobytes())
        encoder.stdin.close()
        if decoder.wait() or encoder.wait(): raise RuntimeError('ffmpeg failed')
    except BaseException:
        decoder.kill(); encoder.kill()
        decoder.wait(); encoder.wait()
        destination.unlink(missing_ok=True)
        raise
    finally:
        decoder.stdout.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('destination'); parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args(); finish_video(args.source, args.destination, args.seed)
if __name__ == '__main__': main()
