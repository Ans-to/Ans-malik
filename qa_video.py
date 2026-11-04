#!/usr/bin/env python3
"""Check encoded video streams and sample contrast/motion; create contact sheet."""
import argparse, subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from forge_python.ffmpeg import get_ffmpeg_exe

def qa(path, sheet, expected_resolution=None):
    result=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-i',str(path)],capture_output=True,text=True)
    info=result.stderr
    if 'Video:' not in info or 'Audio:' not in info: raise ValueError('missing video or audio stream')
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise ValueError('OpenCV could not open video')
    try:
        w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); fps=cap.get(cv2.CAP_PROP_FPS); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if expected_resolution and (w,h)!=expected_resolution: raise ValueError(f'unexpected resolution {w}x{h}')
        if abs(fps-60)>.01 or count<5: raise ValueError(f'bad frame rate or frame count: {fps}, {count}')
        frames=[]; contrasts=[]; deltas=[]
        for i in range(10):
            idx=min(count-1,int((i+.5)*count/10)); cap.set(cv2.CAP_PROP_POS_FRAMES,idx); ok,frame=cap.read()
            if not ok: raise ValueError(f'cannot decode frame {idx}')
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); contrasts.append(float(np.std(gray)))
            cap.set(cv2.CAP_PROP_POS_FRAMES,min(idx+5,count-1)); ok,next_frame=cap.read()
            if ok: deltas.append(float(np.mean(cv2.absdiff(frame,next_frame))))
            frames.append(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
        if min(contrasts)<5: raise ValueError(f'insufficient visual contrast: {contrasts}')
        if max(deltas)<.05: raise ValueError(f'no measurable motion: {deltas}')
        cellw=320; cellh=round(cellw*h/w); sheet_img=Image.new('RGB',(cellw*5,(cellh+24)*2),'#121620'); draw=ImageDraw.Draw(sheet_img)
        for i,frame in enumerate(frames):
            x=(i%5)*cellw; y=(i//5)*(cellh+24); sheet_img.paste(frame.resize((cellw,cellh)),(x,y)); draw.text((x+5,y+cellh+4),f'{(i+.5)*count/fps/10:.2f}s',fill='#F3F4F6')
        sheet_img.save(sheet)
        print(f'PASS: {w}x{h}, {fps:.2f} fps, {count} frames; contrast min={min(contrasts):.1f}, motion max={max(deltas):.2f}; audio stream present')
    finally: cap.release()

def main():
    p=argparse.ArgumentParser(); p.add_argument('video'); p.add_argument('--sheet',default='qa_contact_sheet.png'); p.add_argument('--resolution',help='expected WIDTHxHEIGHT'); a=p.parse_args()
    qa(a.video,a.sheet,tuple(map(int,a.resolution.split('x'))) if a.resolution else None)
if __name__=='__main__': main()
