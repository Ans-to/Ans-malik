"""Deterministic Three.js/GSAP frames captured via Puppeteer SwiftShader."""
import base64
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
class ThreeHero:
    def __init__(self,w,h):
        self.proc=subprocess.Popen(['node',str(ROOT/'web/hero/render.mjs'),str(w),str(h)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        if self.proc.stdout.readline().strip()!='READY':
            self.close(); raise RuntimeError('Three.js renderer failed to start; run npm ci and verify Chromium dependencies')
    def frame(self,frame_idx,fps,word=''):
        self.proc.stdin.write(json.dumps({'frame':frame_idx,'fps':fps,'word':word})+'\n');self.proc.stdin.flush()
        line=self.proc.stdout.readline()
        if not line: raise RuntimeError('Three.js renderer exited unexpectedly')
        img=cv2.imdecode(np.frombuffer(base64.b64decode(line),dtype=np.uint8),cv2.IMREAD_COLOR)
        if img is None: raise RuntimeError('Unable to decode Three.js frame')
        return cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    def close(self):
        if self.proc.poll() is None:
            try: self.proc.stdin.write('{"close":true}\n');self.proc.stdin.flush();self.proc.wait(timeout=10)
            except (BrokenPipeError,subprocess.TimeoutExpired): self.proc.kill();self.proc.wait()
        if self.proc.stdin: self.proc.stdin.close()
        if self.proc.stdout: self.proc.stdout.close()
