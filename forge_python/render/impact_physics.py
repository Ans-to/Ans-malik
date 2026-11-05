"""Deterministic impact timing, camera trauma and refractive shockwaves."""
import bisect
import math
import cv2
import numpy as np

BEATS=(0.0,1.8,3.6,6.0,9.0,12.0,13.4)

def beat_times(duration):
    return [base+t for base in np.arange(0,duration,15.0) for t in BEATS if base+t<duration]

def keyword_times(words):
    return [word['start_ms']/1000 for word in words if len(word.get('word','').strip('.,;:!?'))>=4]

class ImpactPhysicsEngine:
    def __init__(self,width,height,duration,words):
        self.width,self.height=width,height
        self.beats=beat_times(duration)
        self.events=sorted([(t,1.0) for t in self.beats]+[(t,.38) for t in keyword_times(words)])
        self.times=[t for t,_ in self.events]
        yy,xx=np.mgrid[:height,:width].astype(np.float32)
        self.x,self.y=xx,yy
        self.dx=xx-(width-1)/2;self.dy=yy-(height-1)/2
        self.dist=np.sqrt(self.dx*self.dx+self.dy*self.dy)+1e-4
        self.nx=self.dx/self.dist;self.ny=self.dy/self.dist
    def transform(self,frame,t):
        active=[];i=bisect.bisect_right(self.times,t)
        for j in range(i-1,max(-1,i-9),-1):
            age=t-self.events[j][0]
            if age>.40:break
            active.append((age,self.events[j][1]))
        if not active:return frame
        sx=sy=roll=0.
        for age,power in active:
            sx+=power*self.width*.022*math.exp(-12*age)*math.sin(90*age)
            sy+=power*self.height*.016*math.exp(-12*age)*math.cos(83*age)
            roll+=power*4*math.exp(-15*age)*math.cos(75*age)
        mat=cv2.getRotationMatrix2D((self.width/2,self.height/2),roll,1.0)
        mat[0,2]+=sx;mat[1,2]+=sy
        shaken=cv2.warpAffine(frame,mat,(self.width,self.height),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        wave=np.zeros_like(self.dist)
        for age,power in active:
            radius=age*max(self.width,self.height)*2.8
            band=np.exp(-((self.dist-radius)/(max(self.width,self.height)*.018))**2)
            wave+=band*(power*self.width*.012*math.exp(-7*age))
        mx=(self.x+self.nx*wave).astype(np.float32);my=(self.y+self.ny*wave).astype(np.float32)
        return cv2.remap(shaken,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)

def impact_music(duration,sample_rate,words=(),seed=42):
    """Music plus bass impacts and filtered-noise whooshes, before the master bus."""
    n=round(duration*sample_rate);t=np.arange(n,dtype=np.float64)/sample_rate
    music=(.016*np.sin(2*np.pi*55*t)+.009*np.sin(2*np.pi*82.4*t)*(.65+.35*np.sin(2*np.pi*.13*t))).astype(np.float32)
    rng=np.random.default_rng(seed)
    events=sorted([(x,1.0) for x in beat_times(duration)]+[(x,.32) for x in keyword_times(words)])
    for when,level in events:
        i=int(when*sample_rate);size=min(int(.6*sample_rate),n-i)
        if size<=0:continue
        tt=np.arange(size)/sample_rate
        boom=np.sin(2*np.pi*(45*tt+35*(1-np.exp(-9*tt))/9))*np.exp(-8*tt)
        whoosh=rng.standard_normal(size)*np.exp(-16*tt)
        music[i:i+size]+=level*(.09*boom+.012*whoosh).astype(np.float32)
    return music
