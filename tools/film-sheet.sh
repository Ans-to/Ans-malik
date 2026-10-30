#!/usr/bin/env bash
# Contact sheet for the 60 s GPU film: one frame per second, 8×8 grid.
#   bash tools/film-sheet.sh [input.mp4] [output.png]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
ff="${FFMPEG:-$here/ffmpeg}"
src="${1:-$root/gpu-film/out/explainer_1080p.mp4}"
out="${2:-$root/gpu-film/out/contact_sheet.png}"
"$ff" -y -v error -i "$src" -vf "fps=1,scale=480:-1,tile=8x8:margin=6:padding=4" -frames:v 1 "$out"
echo "wrote $out"
