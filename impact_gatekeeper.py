#!/usr/bin/env python3
"""Trailer QA: verify 4 acts are decodable and contain meaningful movement."""
import argparse
import cv2
import numpy as np

def analyze_video(path, minimum_resolution=(1920,1080)):
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('cannot open video')
    try:
        w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=cap.get(cv2.CAP_PROP_FPS);n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if w<minimum_resolution[0] or h<minimum_resolution[1]:raise ValueError('resolution below required minimum')
        if abs(fps-60)>.01 or n<15*fps:raise ValueError('trailer must contain at least 15 seconds at 60 fps')
        motion=[];lum=[]
        for t in (1.3,2.2,4.5,5.3,7.9,9.,11.7,12.6,13.5):
            cap.set(cv2.CAP_PROP_POS_FRAMES,round(t*fps));ok,a=cap.read();ok2,b=cap.read()
            if not ok or not ok2:raise ValueError('cannot decode act')
            a=cv2.resize(a,(320,180));b=cv2.resize(b,(320,180));motion.append(float(np.mean(cv2.absdiff(a,b))));lum.append(float(np.mean(a)))
        if max(motion)<1 or sum(x>.2 for x in motion)<5:raise ValueError(f'insufficient intra-act motion: {motion}')
        if min(lum)<2:raise ValueError(f'blank act samples: {lum}')
        print(f'PASS: {w}x{h} {fps:.2f}fps, samples={n}, motion={motion}, brightness={lum}')
        return {'motion':motion,'luminance':lum}
    finally:cap.release()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('video');args=p.parse_args();analyze_video(args.video)
