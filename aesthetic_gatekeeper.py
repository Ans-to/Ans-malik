#!/usr/bin/env python3
"""Mechanical aesthetic checks: resolution, spatial edge distribution and range.

These heuristics detect some sparse frames; they are not a proxy for taste or
proof of professional quality. Ten frames are sampled across the entire film.
"""
import argparse
import json
from pathlib import Path
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

def motion_pair(previous, current):
    """Estimate a reset and spatial flow variation on adjacent BGR frames.

    Flow variation is a proxy only: optical flow alone cannot prove physical
    depth or distinguish all cuts from fast camera moves.
    """
    def prep(frame):
        frame=cv2.resize(frame,(256,144),interpolation=cv2.INTER_AREA)
        return cv2.GaussianBlur(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(5,5),1.2)
    a,b=prep(previous),prep(current)
    change=float(np.mean(cv2.absdiff(a,b)))/255
    h1=cv2.calcHist([a],[0],None,[32],[0,256]);h2=cv2.calcHist([b],[0],None,[32],[0,256])
    cv2.normalize(h1,h1,1,0,cv2.NORM_L1);cv2.normalize(h2,h2,1,0,cv2.NORM_L1)
    distribution=float(cv2.compareHist(h1,h2,cv2.HISTCMP_BHATTACHARYYA))
    flow=cv2.calcOpticalFlowFarneback(a,b,None,.5,3,15,3,5,1.2,0)
    speeds=np.linalg.norm(flow,axis=2)
    spread=float(np.percentile(speeds,90)-np.percentile(speeds,10))
    return {'reset':change>.22 and distribution>.55,'change':change,'histogram_distance':distribution,'flow_spread':spread}

def detect_reset_spikes(metrics):
    """Find isolated discontinuities against neighboring frame-pair motion."""
    resets=[]
    for i, item in enumerate(metrics):
        neighbors=[metrics[j]['change'] for j in (i-2,i-1,i+1,i+2) if 0<=j<len(metrics)]
        baseline=float(np.median(neighbors)) if neighbors else 0.
        spike=(item['change']>.012 and item['change']>8*max(.001,baseline)
               and (item['histogram_distance']>.06 or item['flow_spread']>3.))
        if item['reset'] or spike: resets.append(i+1)
    return resets

def check_continuity(path):
    """Check every adjacent decoded pair, and summarize optical-flow variation."""
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise ValueError('cannot open video for continuity QA')
    try:
        ok,previous=cap.read()
        if not ok: raise ValueError('cannot decode first frame')
        idx=0; samples=[]; informative=0; count=0; maximum_change=0.
        while True:
            ok,current=cap.read()
            if not ok: break
            idx+=1; metrics=motion_pair(previous,current)
            samples.append(metrics)
            if metrics['flow_spread']>.08: informative+=1
            maximum_change=max(maximum_change,metrics['change']);count+=1;previous=current
        if not count: raise ValueError('not enough frames for continuity QA')
        resets=detect_reset_spikes(samples)
        if resets: raise ValueError(f'possible abrupt frame resets at {resets[:20]}')
        if informative/count<.05: raise ValueError(f'insufficient spatial flow variation ({informative}/{count} adjacent pairs)')
        print(f'PASS continuity: {count} adjacent pairs, no detected reset; flow variation {informative}/{count}; max normalized change {maximum_change:.3f}')
        return {'pairs':count,'resets':resets,'varying_pairs':informative,'max_change':maximum_change}
    finally: cap.release()

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

def check_documentary(path):
    """Validate timing/transition provenance plus sampled transition movement.

    Pixel analysis cannot prove absence of every dissolve or identify objects;
    provenance asserts the renderer selected spatial-only transition types.
    """
    metadata_path=Path(str(path)+'.json')
    if not metadata_path.exists():raise ValueError('documentary timeline metadata is missing')
    data=json.loads(metadata_path.read_text());shots=data.get('shots',[]);transitions=data.get('transitions',[])
    if len(shots)!=11 or len(transitions)!=10:raise ValueError('expected eleven shots and ten transitions')
    if any(not 72 <= s['end_frame']-s['start_frame'] <=96 for s in shots):raise ValueError('shot outside 1.2–1.6 second range')
    if any(x['kind'] not in ('pillar','portal','whip') or x['duration_frames'] not in (8,10) for x in transitions):raise ValueError('unsupported transition')
    if any(shots[i]['end_frame']!=shots[i+1]['start_frame'] or transitions[i]['frame']!=shots[i]['end_frame'] for i in range(10)):raise ValueError('timeline has a gap or mismatched boundary')
    from forge_python.render.documentary_timeline import speed_ramp
    for shot in shots:
        d=(shot['end_frame']-shot['start_frame'])/60
        arrival=speed_ramp(.15,d)-speed_ramp(0,d)
        glide=speed_ramp(.75,d)-speed_ramp(.60,d)
        exit_speed=speed_ramp(d,d)-speed_ramp(d-.15,d)
        if min(arrival,exit_speed)<=4*glide:raise ValueError('speed-ramp curve lacks arrival or exit spike')
    cap=cv2.VideoCapture(str(path));changes=[]
    try:
        if not cap.isOpened():raise ValueError('cannot open video')
        if abs(cap.get(cv2.CAP_PROP_FPS)-60)>.01:raise ValueError('documentary must be 60fps')
        for transition in transitions:
            f=transition['frame'];n=transition['duration_frames'];samples=[]
            for idx in (f-n//2,f,f+n//2-1):
                cap.set(cv2.CAP_PROP_POS_FRAMES,idx);ok,frame=cap.read()
                if not ok:raise ValueError(f'cannot decode transition frame {idx}')
                samples.append(cv2.resize(frame,(160,90),interpolation=cv2.INTER_AREA))
            change=float(np.mean(cv2.absdiff(samples[0],samples[-1])));changes.append(change)
            if change<1.:raise ValueError(f'no visible transition motion at frame {f}')
        print(f'PASS documentary: 11 shots in 1.2–1.6s; 10 spatial transitions; minimum sampled change {min(changes):.2f}. Metadata does not prove semantic content or exclude all dissolves.')
        return {'shots':shots,'transitions':transitions,'transition_change':changes}
    finally:cap.release()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('video');p.add_argument('--samples',type=int,default=10);p.add_argument('--documentary',action='store_true');args=p.parse_args()
    if args.samples<1:p.error('samples must be positive')
    if args.documentary:
        check_documentary(args.video);return
    errors=[]
    for check in (lambda: gatekeep(args.video,args.samples), lambda: check_continuity(args.video)):
        try: check()
        except ValueError as exc:
            errors.append(str(exc))
            print(f'FAIL: {exc}')
    if errors: raise SystemExit(1)
if __name__=='__main__':main()
