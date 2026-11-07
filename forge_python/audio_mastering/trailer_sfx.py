"""Deterministic stereo event stems locked to video frame boundaries."""
import numpy as np
from scipy.signal import butter,sosfilt

def trailer_sfx(duration,sr,transitions,anchors):
    n=round(duration*sr);out=np.zeros((n,2),np.float32);rng=np.random.default_rng(70)
    # 48 Hz drone: a slowly opening filter and +4 dB gain rise by the 88% event.
    climax=next((x['start_frame']/60 for x in anchors if x['text']=='88%'),10.5)
    all_t=np.arange(n)/sr
    raw=sum(np.sin(2*np.pi*48*k*all_t)/k for k in range(1,10)).astype(np.float32)
    block=max(1,sr//4)
    for start in range(0,n,block):
        end=min(n,start+block);p=min(1.,(start/sr)/max(.1,climax));cutoff=120+680*p
        y=sosfilt(butter(2,cutoff,fs=sr,output='sos'),raw[start:end]);gain=.022*10**((4*p)/20)
        out[start:end]+=y[:,None]*gain
    events=[]
    for anchor in anchors:
        frame=anchor['start_frame'];start=round(frame*sr/60);length=min(round(.075*sr),n-start)
        if length<=0:continue
        t=np.arange(length)/sr;click=(np.sin(2*np.pi*3800*t)*np.exp(-t*115)+.3*np.sin(2*np.pi*5200*t)*np.exp(-t*40))*.14
        # Half-sample trigger is avoided: audio onset is at the corresponding frame sample.
        click[0]=.16;out[start:start+length]+=click[:,None];events.append({'frame':frame,'kind':'anchor_click','anchor':anchor['text']})
    for tr in transitions:
        frame=tr['frame'];start=round(frame*sr/60);length=min(round(.45*sr),n-start)
        if length<=0:continue
        t=np.arange(length)/sr
        thud=.19*np.sin(2*np.pi*65*t)*np.exp(-t*16);thud[0]=.08
        noise=rng.standard_normal(length);filtered=np.zeros(length);span=max(.01,length/sr)
        freq=np.where(t<span*.4,250+1550*t/(span*.4),1800-1620*(t-span*.4)/(span*.6))
        # A bank of short band-pass filters tracks the frequency sweep.
        for a in range(0,length,max(1,length//24)):
            b=min(length,a+max(1,length//24));center=freq[min(length-1,(a+b)//2)]
            band=[max(35.,center*.65),min(sr*.45,center*1.35)]
            filtered[a:b]=sosfilt(butter(2,band,btype='bandpass',fs=sr,output='sos'),noise[a:b])
        tone=np.sin(2*np.pi*np.cumsum(freq)/sr)
        sweep=(filtered*.08+tone*.026)*np.exp(-t*7)
        pan=np.linspace(1,0,length);out[start:start+length,0]+=thud+sweep*pan;out[start:start+length,1]+=thud+sweep*(1-pan)
        events.append({'frame':frame,'kind':'transition_thud','transition':tr['kind']})
    return out,events
