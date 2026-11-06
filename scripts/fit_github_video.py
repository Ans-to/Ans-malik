#!/usr/bin/env python3
"""Keep a complete MP4 below GitHub's ordinary 100 MiB blob limit.

Re-encode only if needed; preserve the original until a candidate fits. The
workflow runs audiovisual QA on the chosen output after this step.
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe

LIMIT=95*1024*1024

def fit(path,limit=LIMIT):
    path=Path(path)
    if path.stat().st_size<=limit:
        print(f'Video already fits: {path.stat().st_size} bytes');return
    with tempfile.TemporaryDirectory(prefix='video-fit-',dir=path.parent) as d:
        candidate=Path(d)/'candidate.mp4'
        for crf in (20,23,26,29,32):
            print(f'Re-encoding to fit GitHub (CRF {crf})',flush=True)
            subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(path),'-map','0:v:0','-map','0:a?', '-c:v','libx264','-preset','medium','-crf',str(crf),'-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(candidate)],check=True)
            size=candidate.stat().st_size;print(f'Candidate: {size} bytes',flush=True)
            if size<=limit:
                os.replace(candidate,path);return
        raise RuntimeError('Could not fit the full video under the GitHub limit; use LFS or external storage')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('video');args=parser.parse_args();fit(args.video)
