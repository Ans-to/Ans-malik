"""Capture full-screen shaded Three.js shots in headless Chromium."""
import base64,json,subprocess
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
class DocumentaryRenderer:
    def __init__(self,width,height):
        self.proc=subprocess.Popen(['node',str(ROOT/'web/documentary/render.mjs'),str(width),str(height)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        if self.proc.stdout.readline().strip()!='READY':self.close();raise RuntimeError('Documentary renderer failed to start')
    def frame(self,shot,u,d,pulse=0):
        self.proc.stdin.write(json.dumps({'shot':shot,'u':u,'d':d,'pulse':pulse})+'\n');self.proc.stdin.flush();line=self.proc.stdout.readline()
        if not line:raise RuntimeError('Documentary renderer exited')
        image=cv2.imdecode(np.frombuffer(base64.b64decode(line),np.uint8),cv2.IMREAD_COLOR)
        if image is None:raise RuntimeError('Cannot decode frame')
        return cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    def close(self):
        if self.proc.poll() is None:
            try:self.proc.stdin.write('{"close":true}\n');self.proc.stdin.flush();self.proc.wait(timeout=10)
            except (BrokenPipeError,subprocess.TimeoutExpired):self.proc.kill();self.proc.wait()
        if self.proc.stdin:self.proc.stdin.close()
        if self.proc.stdout:self.proc.stdout.close()
