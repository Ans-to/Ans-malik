#!/usr/bin/env python3
"""QA for deliberately hard-cut, high-impact videos; cuts are expected here."""
import argparse
import cv2
import numpy as np

BEAT_CENTERS=(.9,2.7,4.8,7.5,10.5,13.5)

def analyze_video(path, minimum_resolution=(1920,1080)):
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise ValueError('cannot open video')
    try:
        w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=cap.get(cv2.CAP_PROP_FPS);n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if w<minimum_resolution[0] or h<minimum_resolution[1]: raise ValueError(f'resolution {w}x{h} below required {minimum_resolution}')
        if abs(fps-60)>.01 or n<round(15*fps):raise ValueError('showcase must contain at least 15 seconds at 60 fps')
        beat_colors=[]; luminances=[]
        for t in BEAT_CENTERS:
            cap.set(cv2.CAP_PROP_POS_FRAMES,round(t*fps));ok,frame=cap.read()
            if not ok:raise ValueError(f'cannot decode beat at {t}s')
            small=cv2.resize(frame,(160,90),interpolation=cv2.INTER_AREA)
            beat_colors.append(np.mean(small,axis=(0,1)));luminances.append(float(np.mean(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY))))
        # Palette changes and ivory inversion must be observable rather than merely requested.
        if max(luminances)-min(luminances)<70:raise ValueError(f'insufficient light/dark palette inversion: {luminances}')
        if np.linalg.norm(beat_colors[0]-beat_colors[1])<50:raise ValueError('first inversion has insufficient color separation')
        # Sample image motion at six frames within each beat; deliberate hard cuts are allowed.
        motion=[]
        for t in (.15,.32,2.,4.,6.2,7.,9.3,10.,12.1,13.45):
            idx=round(t*fps);cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,a=cap.read();ok2,b=cap.read()
            if not ok or not ok2:raise ValueError(f'cannot sample motion at {t}s')
            a=cv2.resize(a,(320,180));b=cv2.resize(b,(320,180))
            motion.append(float(np.mean(cv2.absdiff(a,b))))
        if max(motion)<2 or sum(x>.35 for x in motion)<4:raise ValueError(f'insufficient intra-beat motion: {motion}')
        print(f'PASS: {w}x{h} {fps:.2f}fps; beat luminance {[round(x,1) for x in luminances]}; motion peak {max(motion):.2f}')
        return {'resolution':[w,h],'fps':fps,'luminances':luminances,'motion':motion}
    finally:cap.release()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('video');args=p.parse_args();analyze_video(args.video)
if __name__=='__main__':main()
