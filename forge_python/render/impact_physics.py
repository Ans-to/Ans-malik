"""Deterministic impact timing, camera trauma and refractive shockwaves."""
import bisect
import math
import cv2
import numpy as np

BEATS=(0.0,1.2,3.8,5.2,7.6,11.4,12.4)

def beat_times(duration):
    return [base+t for base in np.arange(0,duration,15.0) for t in BEATS if base+t<duration]

def keyword_times(words):
    return [word['start_ms']/1000 for word in words if len(word.get('word','').strip('.,;:!?'))>=4]

class ImpactPhysicsEngine:
    def __init__(self,width,height,duration,words):
        self.width,self.height=width,height
        self.beats=beat_times(duration)
        self.events=[(t,1.0) for t in self.beats]
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
        if not active and not (11.4 <= t%15 < 12.4):return frame
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
        # Gravitational lens leading into the final singularity detonation.
        phase=t%15
        if 11.4<=phase<12.4:
            strength=math.sin(math.pi*(phase-11.4))*self.width*.035
            lens=strength*np.exp(-self.dist/(self.width*.22))
            mx+=self.nx*lens;my+=self.ny*lens
        return cv2.remap(shaken,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)

def impact_music(duration,sample_rate,words=(),seed=42):
    """Trailer brass, rising sweeps and crystalline foley synchronized to impacts."""
    from scipy.signal import sawtooth, chirp, butter, sosfilt
    from pedalboard import Pedalboard, Distortion, Reverb
    n=round(duration*sample_rate);music=np.zeros(n,dtype=np.float32);rng=np.random.default_rng(seed)
    music+=.008*np.sin(2*np.pi*55*np.arange(n)/sample_rate).astype(np.float32)
    board=Pedalboard([Distortion(drive_db=20),Reverb(room_size=.8,wet_level=.3)])
    for when in beat_times(duration):
        i=round(when*sample_rate);size=min(round(1.4*sample_rate),n-i)
        if size<=0:continue
        t=np.arange(size)/sample_rate;env=np.minimum(1,t*30)*np.exp(-t*2.2)
        brass=(sawtooth(2*np.pi*55*t)+.7*sawtooth(2*np.pi*55.8*t)+.5*sawtooth(2*np.pi*110*t))*env*.10
        brass=board(brass.astype(np.float32),sample_rate,reset=True)
        noise=sosfilt(butter(3,2500,fs=sample_rate,btype='highpass',output='sos'),rng.standard_normal(size))*np.exp(-t*14)*.08
        music[i:i+size]+=(brass*.38+noise).astype(np.float32)
        # Build for up to 1.5s before each event, clipped at the timeline start.
        start=max(0,i-round(1.5*sample_rate)); count=i-start
        if count:
            rt=np.arange(count)/sample_rate;span=count/sample_rate
            sweep=chirp(rt,f0=100,f1=1800,t1=max(span,.01),method='logarithmic')
            air=sosfilt(butter(2,1400,fs=sample_rate,btype='highpass',output='sos'),rng.standard_normal(count))
            music[start:i]+=((sweep*.028+air*.018)*(rt/max(span,.01))**2).astype(np.float32)
    return music
