"""Capture deterministic full-screen Three.js/GLSL compositions via Chromium."""
import base64,json,subprocess
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
class ImpactRenderer:
    def __init__(self,width,height,topic,document_path):
        rel=Path(document_path).resolve().relative_to(ROOT).as_posix()
        self.proc=subprocess.Popen(['node',str(ROOT/'web/impact/render.mjs'),str(width),str(height),topic,rel],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        if self.proc.stdout.readline().strip()!='READY':
            self.close();raise RuntimeError('Impact renderer failed to start; run npm ci and check WebGL')
    def frame(self,index,fps,word='',word_age=1,levels=(0,0,0),word_id=-1,word_progress=0):
        self.proc.stdin.write(json.dumps({'frame':index,'fps':fps,'word':word,'wordAge':word_age,'levels':list(map(float,levels)),'wordId':word_id,'wordProgress':word_progress})+'\n');self.proc.stdin.flush()
        line=self.proc.stdout.readline()
        if not line:raise RuntimeError('Impact renderer unexpectedly exited')
        img=cv2.imdecode(np.frombuffer(base64.b64decode(line),np.uint8),cv2.IMREAD_COLOR)
        if img is None:raise RuntimeError('Could not decode impact frame')
        return cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    def close(self):
        if self.proc.poll() is None:
            try:self.proc.stdin.write('{"close":true}\n');self.proc.stdin.flush();self.proc.wait(timeout=10)
            except (BrokenPipeError,subprocess.TimeoutExpired):self.proc.kill();self.proc.wait()
        if self.proc.stdin:self.proc.stdin.close()
        if self.proc.stdout:self.proc.stdout.close()
