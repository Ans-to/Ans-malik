"""Candidate acoustic onset near a speech-service word event.

A local energy/flux peak is not a phoneme classifier. It can correspond to a
neighboring syllable, breath or noise and may be absent for a quiet consonant.
The returned confidence and fallback reason must remain visible to callers.
"""
import numpy as np
from scipy.signal import stft, find_peaks


def estimate_onset(audio,sample_rate,estimate_sample):
    x=np.asarray(audio,dtype=np.float64).reshape(-1);sr=int(sample_rate)
    if sr<=0 or not len(x) or not 0<=estimate_sample<len(x):raise ValueError('invalid audio or event sample')
    lo=max(0,int(estimate_sample-round(.120*sr)));hi=min(len(x),int(estimate_sample+round(.150*sr)))
    window=x[lo:hi];n=max(64,round(.012*sr));hop=max(1,round(.002*sr))
    if len(window)<n*2 or np.max(np.abs(window))<1e-5:
        return {'sample':int(estimate_sample),'status':'fallback','reason':'insufficient audible energy','rms_rise':0.0,'flux':0.0}
    _,times,z=stft(window,fs=sr,nperseg=n,noverlap=n-hop,boundary=None,padded=False)
    mag=np.abs(z);flux=np.r_[0,np.maximum(np.diff(mag,axis=1),0).sum(axis=0)]
    idx=np.maximum(0,np.minimum(len(window)-n,np.rint(times*sr-n/2).astype(int)))
    power=np.r_[0,np.cumsum(window*window)];rms=np.sqrt(np.maximum(0,(power[idx+n]-power[idx])/n))
    rise=np.r_[0,np.diff(rms)];max_r=float(np.max(rise));max_f=float(np.max(flux))
    if max_r<=1e-8 or max_f<=1e-8:
        return {'sample':int(estimate_sample),'status':'fallback','reason':'no rising energy and spectral flux','rms_rise':0.0,'flux':0.0}
    # Select genuine local rising-energy/flux peaks with a proximity preference.
    score=np.maximum(rise,0)/max_r+flux/max_f
    peaks,_=find_peaks(score)
    candidates=[j for j in peaks if rise[j]>max_r*.08 and flux[j]>max_f*.05]
    if not candidates:return {'sample':int(estimate_sample),'status':'fallback','reason':'no joint RMS and flux peak','rms_rise':0.0,'flux':0.0}
    target=(estimate_sample-lo)/sr
    best=max(candidates,key=lambda j:float(score[j])/(1+abs(float(times[j])-target)*10))
    sample=int(np.clip(lo+round(times[best]*sr),0,len(x)-1))
    return {'sample':sample,'status':'snapped','reason':'local joint energy/flux peak; not verified phoneme boundary','rms_rise':float(rise[best]),'flux':float(flux[best]),'edge_sample':int(estimate_sample)}
