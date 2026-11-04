#!/usr/bin/env python3
"""Mechanical aesthetic checks: resolution, spatial edge distribution and range.

These heuristics detect some sparse frames; they are not a proxy for taste or
proof of professional quality. Ten frames are sampled across the entire film.
"""
import argparse
import cv2
import numpy as np


def analyze_frame(frame):
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    # Normalize spatial scale so thresholds are comparable at larger resolutions.
    gray=cv2.resize(gray,(960,540),interpolation=cv2.INTER_AREA)
    # Suppress fine grain so it cannot masquerade as visual information.
    edge_source=cv2.GaussianBlur(gray,(0,0),2)
    gx=cv2.Sobel(edge_source,cv2.CV_32F,1,0,ksize=3); gy=cv2.Sobel(edge_source,cv2.CV_32F,0,1,ksize=3)
    edges=cv2.magnitude(gx,gy)>20
    density=float(np.mean(edges))
    cells=[float(np.mean(edges[y*180:(y+1)*180,x*320:(x+1)*320])) for y in range(3) for x in range(3)]
    covered=sum(value>=0.005 for value in cells)
    dark=float(np.mean(gray<40)); mid=float(np.mean((gray>=40)&(gray<160))); highlights=float(np.mean(gray>=160))
    failures=[]
    if density<.015: failures.append(f'edge density {density:.4f} < .015')
    if covered<4: failures.append(f'edge coverage {covered}/9 cells < 4/9')
    if dark<.05 or mid<.01 or highlights<.001: failures.append(f'range dark/mid/high {dark:.3f}/{mid:.3f}/{highlights:.3f} below minimum')
    return {'edge_density':density,'cells':cells,'covered':covered,'dark':dark,'mid':mid,'highlights':highlights,'failures':failures}

def gatekeep(path,samples=10):
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise ValueError('cannot open video')
    try:
        w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if w<1920 or h<1080: raise ValueError(f'resolution {w}x{h} is below 1920x1080')
        if n<=0: raise ValueError('empty video')
        reports=[]
        for i in range(samples):
            idx=min(n-1,int((i+.5)*n/samples));cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,frame=cap.read()
            if not ok: raise ValueError(f'failed to decode frame {idx}')
            result=analyze_frame(frame);result['frame']=idx;reports.append(result)
        bad=[f"frame {x['frame']}: {', '.join(x['failures'])}" for x in reports if x['failures']]
        if bad: raise ValueError('Aesthetic gate failed:\n'+'\n'.join(bad))
        print(f'PASS: {len(reports)} samples, minimum edge density {min(r["edge_density"] for r in reports):.4f}, minimum cell coverage {min(r["covered"] for r in reports)}/9')
        return reports
    finally: cap.release()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('video');p.add_argument('--samples',type=int,default=10);args=p.parse_args()
    if args.samples<1:p.error('samples must be positive')
    gatekeep(args.video,args.samples)
if __name__=='__main__':main()
