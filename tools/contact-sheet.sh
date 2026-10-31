#!/usr/bin/env bash
# Build a 3×2 contact sheet from the finished film (needs ffmpeg).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
ff="${FFMPEG:-$here/ffmpeg}"
src="${1:-$root/motion/out/motion-by-code-1080p.mp4}"
out="${2:-$root/motion/out/contact-sheet.png}"
fps=3   # pull one frame every ~0.33 s, then tile
"$ff" -y -v error -i "$src" -vf "fps=$fps,scale=640:-1,tile=4x6" -frames:v 1 "$out"
echo "wrote $out"
