"""Deterministic shot timing, speed ramps and spatial-only physical transitions."""
import bisect, math, re
import cv2
import numpy as np

FPS=60
N_SHOTS=11
TRANSITIONS=('pillar','portal','whip')
KEYWORDS={'1971','nixon','closed','gold','banks','dollars','ledgers','debt','trade','2022','dollar','eighty','eight','foreign','exchange'}

def cubic_bezier(t):
    t=max(0.,min(1.,t));lo=0.;hi=1.
    for _ in range(16):
        q=(lo+hi)/2;x=3*(1-q)**2*q*.85+3*(1-q)*q*q*.15+q**3
        if x<t:lo=q
        else:hi=q
    q=(lo+hi)/2
    return 3*(1-q)*q*q+q**3

def speed_ramp(u,duration):
    arrive=cubic_bezier(u/.068)
    glide=max(0.,min(1.,(u-.068)/max(.01,duration-.136)))
    depart=cubic_bezier((u-(duration-.068))/.068)
    return .7*arrive+.15*glide+.8*depart

def make_timeline(duration,words=()):
    total=round(duration*FPS); candidates=[round(x['start_ms']*FPS/1000) for x in words if any(token in KEYWORDS for token in re.findall(r'[a-z0-9]+',x.get('word','').lower()))]
    # Eleven shots, each 72–96 frames when feasible. Snap to nearby meaningful
    # word boundaries, subject to bounds on both remaining and previous shots.
    if not N_SHOTS*72 <= total <= N_SHOTS*96:raise ValueError('duration must allow eleven shots of 1.2–1.6 seconds')
    bounds=[0]
    for i in range(1,N_SHOTS):
        ideal=round(total*i/N_SHOTS);low=max(bounds[-1]+72,total-(N_SHOTS-i)*96);high=min(bounds[-1]+96,total-(N_SHOTS-i)*72)
        choices=[x for x in candidates if low<=x<=high and abs(x-ideal)<=9]
        bounds.append(min(choices,key=lambda x:abs(x-ideal)) if choices else max(low,min(high,ideal)))
    bounds.append(total)
    shots=[{'index':i,'start_frame':bounds[i],'end_frame':bounds[i+1]} for i in range(N_SHOTS)]
    transitions=[{'frame':bounds[i],'kind':TRANSITIONS[(i-1)%3],'duration_frames':8 if TRANSITIONS[(i-1)%3]=='whip' else 10} for i in range(1,N_SHOTS)]
    return shots,transitions

def active_shot(shots,frame):return min(len(shots)-1,max(0,bisect.bisect_right([s['start_frame'] for s in shots],frame)-1))

def physical_transition(old,new,progress,kind):
    """Spatial replacement only: masks/occlusion or a panning stitched canvas.

    No full-frame alpha cross-dissolve. Inputs are RGB uint8, same shape.
    """
    h,w=old.shape[:2];p=max(0.,min(1.,progress));ease=cubic_bezier(p)
    if kind=='pillar':
        x=round((-0.12+1.24*ease)*w);out=old.copy();out[:,:max(0,min(w,x))]=new[:,:max(0,min(w,x))]
        # Foreground column, lit from one side; directional blur is confined to it.
        strip=max(1,round(w*.12));left=max(0,x-strip//2);right=min(w,x+strip//2)
        if right>left:
            grad=np.linspace(.12,.025,right-left,dtype=np.float32)[None,:,None]
            out[:,left:right]=(np.array([42,38,34],dtype=np.float32)*grad/.12).clip(0,255).astype(np.uint8)
            out=cv2.blur(out,(max(1,round(w*.012))|1,1))
        return out
    if kind=='portal':
        out=old.copy();hw=round(w*.55*ease);hh=round(h*.55*ease);cx=w//2;cy=h//2
        x0=max(0,cx-hw);x1=min(w,cx+hw);y0=max(0,cy-hh);y1=min(h,cy+hh)
        if x1>x0 and y1>y0:
            out[y0:y1,x0:x1]=new[y0:y1,x0:x1]
            if 0<p<.98:cv2.rectangle(out,(x0,y0),(max(x0,x1-1),max(y0,y1-1)),(176,134,75),max(1,round(w*.003)))
        return out
    if kind=='whip':
        canvas=np.concatenate((old,new),axis=1);x=min(w,max(0,round(ease*w)));out=canvas[:,x:x+w].copy()
        # 20 taps in the direction of travel, strongest in the middle of the whip.
        span=max(1,round(w*.055*math.sin(math.pi*p)));kernel=np.zeros((1,span*2+1),np.float32)
        for offset in np.linspace(-span,span,20).astype(int):kernel[0,offset+span]+=1/20
        out=cv2.filter2D(out,-1,kernel,borderType=cv2.BORDER_REFLECT_101)
        shift=round(span*.08)
        if shift:out[:,:,0]=np.roll(out[:,:,0],shift,axis=1);out[:,:,2]=np.roll(out[:,:,2],-shift,axis=1)
        return out
    raise ValueError(f'unknown transition {kind}')

ANCHOR_DEFINITIONS=(('1971',('1971',)),('CLOSED',('closed',)),('GOLD WINDOW',('gold','window')),('DIGITAL LEDGERS',('digital','ledgers')),('DEBT TOWERS',('debt','towers')),('FOUR HUBS',('four','hubs')),('88%',('eighty','eight','percent')))

def anchor_events(words):
    """Resolve visible anchors from actual engine/aligner word timestamps."""
    tokens=[]
    for item in words:
        normalized=re.findall(r'[a-z0-9]+',item.get('word','').lower())
        for token in normalized:tokens.append((token,item))
    events=[]
    for label,phrase in ANCHOR_DEFINITIONS:
        found=None
        for i in range(len(tokens)):
            # eSpeak may report only 'eighty' for its hyphenated word.
            needle=phrase
            if label=='88%' and i+1<len(tokens) and tokens[i][0]=='eighty' and tokens[i+1][0]=='percent':needle=('eighty','percent')
            if tuple(x[0] for x in tokens[i:i+len(needle)])==needle:
                first=tokens[i][1];last=tokens[i+len(needle)-1][1];found=(first,last);break
        if found:
            first,last=found
            start=math.ceil(first['start_ms']*FPS/1000);end=max(start+1,math.ceil(last['end_ms']*FPS/1000))
            events.append({'text':label,'start_frame':start,'end_frame':end,'source_start_ms':first['start_ms'],'source_end_ms':last['end_ms']})
    return sorted(events,key=lambda x:x['start_frame'])

def make_v2_timeline(words,duration=12.):
    """Shots advance at the end of selected spoken anchor phrases."""
    total=round(duration*FPS);anchors=anchor_events(words)
    if len(anchors)!=len(ANCHOR_DEFINITIONS):
        missing=set(a[0] for a in ANCHOR_DEFINITIONS)-set(a['text'] for a in anchors)
        raise ValueError(f'Cannot time required spoken anchors: {sorted(missing)}')
    # The final 88% scene begins after the preceding spoken word's syllable.
    boundary_anchors=anchors[:-1]
    bounds=[0]+[min(total-1,a['end_frame']) for a in boundary_anchors]
    final_anchor=anchors[-1]; before=[w for w in words if math.ceil(w['end_ms']*FPS/1000)<=final_anchor['start_frame']]
    if before:bounds.append(math.ceil(before[-1]['end_ms']*FPS/1000))
    bounds.append(total)
    if any(b<=a for a,b in zip(bounds,bounds[1:])):raise ValueError('word-timed shot boundaries overlap')
    shots=[{'index':i,'start_frame':bounds[i],'end_frame':bounds[i+1]} for i in range(len(bounds)-1)]
    transitions=[{'frame':bounds[i], 'kind':TRANSITIONS[(i-1)%3], 'duration_frames':4 if TRANSITIONS[(i-1)%3]=='whip' else 5, 'aligned_to':'spoken word end'} for i in range(1,len(bounds)-1)]
    return shots,transitions,anchors
