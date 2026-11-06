"""Per-pixel procedural cosmic visuals, rendered on the CPU with Numba.

The black-hole lens uses a screen-space approximation, not a GR integrator.
All four acts use continuous fields instead of polygonal geometry or sprites.
"""
import math
import cv2
import numpy as np
from numba import njit, prange
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

@njit(cache=True,fastmath=True)
def hash3(x,y,z):
    n=math.sin(x*127.1+y*311.7+z*74.7)*43758.5453
    return n-math.floor(n)

@njit(cache=True,fastmath=True)
def gradient(ix,iy,iz,x,y,z):
    h=int(hash3(ix,iy,iz)*12.)
    if h<4: return (x if h&1 else -x)+(y if h&2 else -y)
    if h<8: return (x if h&1 else -x)+(z if h&2 else -z)
    return (y if h&1 else -y)+(z if h&2 else -z)

@njit(cache=True,fastmath=True)
def noise(x,y,z):
    ix=math.floor(x);iy=math.floor(y);iz=math.floor(z)
    x-=ix;y-=iy;z-=iz
    u=x*x*x*(x*(x*6-15)+10);v=y*y*y*(y*(y*6-15)+10);w=z*z*z*(z*(z*6-15)+10)
    a=gradient(ix,iy,iz,x,y,z)*(1-u)+gradient(ix+1,iy,iz,x-1,y,z)*u
    b=gradient(ix,iy+1,iz,x,y-1,z)*(1-u)+gradient(ix+1,iy+1,iz,x-1,y-1,z)*u
    c=gradient(ix,iy,iz+1,x,y,z-1)*(1-u)+gradient(ix+1,iy,iz+1,x-1,y,z-1)*u
    d=gradient(ix,iy+1,iz+1,x,y-1,z-1)*(1-u)+gradient(ix+1,iy+1,iz+1,x-1,y-1,z-1)*u
    return .5+.5*((a*(1-v)+b*v)*(1-w)+(c*(1-v)+d*v)*w)

@njit(cache=True,fastmath=True)
def fbm(x,y,z):
    value=0.;weight=.5
    for i in range(6):
        value+=weight*noise(x,y,z);x=x*2.03+11.1;y=y*2.01+5.7;z=z*2.02+3.9;weight*=.5
    return value

@njit(cache=True,fastmath=True)
def cellular_edge(x,y,z):
    ix=math.floor(x);iy=math.floor(y);iz=math.floor(z);first=100.;second=100.
    for dz in range(-1,2):
        for dy in range(-1,2):
            for dx in range(-1,2):
                a=ix+dx;b=iy+dy;c=iz+dz
                px=a+hash3(a,b,c);py=b+hash3(a+17,b+4,c);pz=c+hash3(a+9,b+3,c+11)
                dist=(x-px)**2+(y-py)**2+(z-pz)**2
                if dist<first:second=first;first=dist
                elif dist<second:second=dist
    return math.sqrt(second)-math.sqrt(first)

@njit(cache=True,fastmath=True)
def clamp(x):return min(1.,max(0.,x))

@njit(cache=True,fastmath=True)
def blackbody(temp,wavelength):
    # Relative spectral radiance from Planck's law, sampled at RGB wavelengths.
    lam=wavelength*1e-9
    return (lam**-5)/(math.exp(.01438777/(lam*temp))-1.)

@njit(cache=True,fastmath=True)
def photon_bend(x,y):
    # Integrate an inverse-square transverse bending approximation along a
    # ray past a compact mass. It is not a Schwarzschild geodesic solver.
    px=0.;py=0.;pz=-3.;vx=x*.25;vy=y*.25;vz=1.
    for step in range(12):
        r2=px*px+py*py+pz*pz+.18
        inv=.055/(r2*math.sqrt(r2))
        vx-=px*inv;vy-=py*inv;vz-=pz*inv
        px+=vx*.3;py+=vy*.3;pz+=vz*.3
    return px-x*.9,py-y*.9

@njit(parallel=True,fastmath=True,cache=True)
def render_shader(w,h,t):
    """Return a continuous RGB image; fixed act boundaries match the soundtrack."""
    out=np.empty((h,w,3),np.uint8);phase=t%15.
    for j in prange(h):
        for i in range(w):
            x=(i/w-.5)*2*w/h;y=(.5-j/h)*2;r=math.sqrt(x*x+y*y)+1e-6
            rr=0.;gg=0.;bb=0.
            if phase<3.8:
                # A ray-sphere intersection with continuous FBM displacement and
                # Voronoi cracks. Rolling smoke is integrated along short rays.
                age=phase; radius=.69+min(age,1.2)*.06
                camz=2.8-age*.22; impact=math.sqrt(x*x+y*y);s=math.sqrt(max(0.,radius*radius-impact*impact))
                tx=x*2.4+age*.15;ty=y*2.4;tz=(s+age*.14)*2.4
                # Four density samples along the view ray approximate smoke extinction.
                smoke=0.
                for step in range(4):
                    depth=step*.45
                    smoke+=fbm(x*2.3+age*.18,y*2.3,depth+age*.4)*.25
                haze=max(0.,smoke-.37)*.13*math.exp(-r*.65)
                rr=.016+haze*1.25;gg=.008+haze*.57;bb=.014+haze*.39
                # March a displaced spherical SDF along the view ray.
                surface=False
                if impact<radius+.10:
                    depth=2.0
                    for step in range(18):
                        displacement=(fbm(x*5,y*5,depth*5+age*.2)-.5)*.13
                        distance=math.sqrt(x*x+y*y+depth*depth)-radius+displacement
                        if distance<.014:
                            surface=True;s=max(0.,depth);break
                        depth-=max(.025,distance*.7)
                        if depth<-.2:break
                if surface:
                    texture=fbm(tx*2,ty*2,tz*2);edge=cellular_edge(tx*1.9,ty*1.9,tz*1.9)
                    rupture=clamp((age-.8)*.7);crack=math.exp(-edge*(45.-rupture*25.))
                    rough=.045+texture*.115;lit=.35+.65*max(0.,(-x*.35+y*.48+s*.8)/radius)
                    dissolve=clamp((age-1.2)*.65)
                    open_crust=clamp((crack+texture*.5-.38)*dissolve*2.)
                    heat=(crack*(.65+1.8*rupture)+open_crust*.9)*(1.0-.35*clamp((age-2.2)/1.6))
                    rr+=rough*lit+heat*1.45;gg+=rough*lit*.45+heat*.65;bb+=rough*lit*.35+heat*.18
                # Radial smoke-attenuated light shafts from the rupturing core.
                angle=math.atan2(y,x);rays=max(0.,math.sin(angle*13+smoke*7+age*.3))**13
                shaft=math.exp(-r*1.45)*rays*max(0.,age-.8)*.13
                flare_age=max(0.,age-1.2)
                blast=math.exp(-((r-radius-flare_age*.42)/(.08+flare_age*.05))**2)*clamp(flare_age*2)*(.25+.75*smoke)
                rr+=shaft*1.5+blast*1.2;gg+=shaft*.78+blast*.42;bb+=shaft*.32+blast*.08
            elif phase<7.6:
                # Continuous lensed disk projection: two strongly bent image arcs
                # plus the direct tilted disk. An artistic approximation, not GR.
                age=phase-3.8; spin=age*.35
                bx,by=photon_bend(x,y)
                qx=x*.97+bx*.02;qy=y+by*.02;rad=math.sqrt(qx*qx+qy*qy)+1e-6
                lens=.66;ang=math.atan2(qy,qx)
                warp=fbm(qx*2.1+spin,qy*3.,spin*.7)
                streak=fbm(qx*4.1+spin*1.5,qy*7.+warp,spin*.9)
                mid=.07*math.sin(qx*2+spin)
                direct=math.exp(-((qy-mid)/(.072+.03*abs(qx)))**2)*math.exp(-((abs(qx)-1.05)/.95)**2)
                arc_y=.44*math.sqrt(max(0.,1.-min(1.,(qx/1.45)**2)))+.10
                top=math.exp(-((qy-arc_y)/.065)**2)*math.exp(-((abs(qx)-.58)/1.05)**2)
                bottom=math.exp(-((qy+arc_y*.78)/.060)**2)*math.exp(-((abs(qx)-.58)/1.05)**2)
                disk=(direct+top*.8+bottom*.72)*clamp((abs(qx)+abs(qy)-.32)*3.)
                doppler=clamp(.75-qx*.35);dust=math.exp(-max(0.,.58-streak)*3.5)
                heat=disk*(.55+1.7*warp)*dust*(.45+1.3*doppler)
                # Hot inner rim and attenuating red dust, no point particles.
                photon=math.exp(-((rad-lens)/.035)**2)*(.35+.65*doppler)
                if rad<lens*.84:heat=0.;photon=0.
                temperature=2200+5500*clamp(1.-abs(qx)*.42)*(.8+.3*doppler)
                red=blackbody(temperature,610.);green=blackbody(temperature,550.);blue=blackbody(temperature,460.);peak=max(red,green,blue)
                rr=.006+heat*1.55*red/peak+photon*1.4
                gg=.006+heat*.9*green/peak+photon*.82
                bb=.012+heat*.5*blue/peak+photon*.33
            elif phase<11.4:
                age=phase-7.6;roll=.48*math.sin(age*.9);xx=x*math.cos(roll)-y*math.sin(roll);yy=x*math.sin(roll)+y*math.cos(roll)
                # Layered, warped 3D folding with spectral thin-film-style color.
                z=age*1.8;f=fbm(xx*1.3+z*.12,yy*1.3,z*.45)
                a=xx+1.15*(f-.5);b=yy+.9*(fbm(xx*1.4+f,yy*1.4,z*.4)-.5)
                glow=0.;filament=0.
                for k in range(5):
                    scale=1.2+k*.48
                    wx=abs(math.sin(a*scale+z*.42+math.sin(b*1.7)));wy=abs(math.sin(b*scale-z*.27+math.sin(a*1.3)))
                    ridge=math.exp(-abs(wx-wy)*18.)
                    depth=1./(1+k*.7);filament+=ridge*depth
                    glow+=math.exp(-abs(wx+wy-.9)*5.)*depth
                # Integrate a short moving column of warped nebular density.
                cloud=0.
                for step in range(4):
                    depth=z*.55+step*.5
                    cloud+=fbm(a*2.2+depth*.1,b*2.2,depth)*.25
                glow+=max(0.,cloud-.42)*1.4
                filament*=.19*(.7+.3*math.sin(age*3+f*5))
                rr=.02+glow*.055+filament*(.75+.65*math.sin(cloud*7)**2)
                gg=.025+glow*.15+filament*(.65+.45*math.sin(cloud*9+1)**2)
                bb=.045+glow*.20+filament*(.35+.45*math.sin(cloud*8+2)**2)
            else:
                age=phase-11.4;rot=math.atan2(y,x);cloud=fbm(x*2+age*.28,y*2,age*.4)
                core=math.exp(-r*r/(.15+.06*math.sin(age)**2));ring=math.exp(-((r-.45-age*.1)/.16)**2)
                beam=math.exp(-abs(y)*9.)*math.exp(-abs(x)*.6)
                radiance=(.18+cloud*.8)*ring+core*1.8+beam*.35
                rr=.009+radiance*1.3;gg=.008+radiance*.62;bb=.017+radiance*.23
            out[j,i,0]=int(255*clamp(rr));out[j,i,1]=int(255*clamp(gg));out[j,i,2]=int(255*clamp(bb))
    return out

class CosmicRenderer:
    def __init__(self,width,height,internal_width=None):
        self.width,self.height=width,height
        self.iw=width if internal_width is None else min(internal_width,width);self.ih=max(1,round(self.iw*height/width))
        self.mask=self._title_mask()
    def _title_mask(self):
        # 60px and +0.55em tracking on a 1080p-high canvas.
        font_size=max(8,round(60*self.height/1080));tracking=font_size*.55
        font=ImageFont.truetype(str(Path(__file__).resolve().parents[2]/'shared_workspace/fonts/InstrumentSerif-Italic.ttf'),font_size)
        text='ONLY PHYSICS SURVIVES';length=sum(font.getlength(c) for c in text)+tracking*(len(text)-1)
        mask=Image.new('L',(self.width,self.height));draw=ImageDraw.Draw(mask);x=(self.width-length)/2;y=self.height*.49-font_size*.5
        for c in text:draw.text((round(x),round(y)),c,font=font,fill=255);x+=font.getlength(c)+tracking
        return np.asarray(mask,dtype=np.float32)/255.
    def frame(self,t):
        image=render_shader(self.iw,self.ih,t)
        image=cv2.resize(image,(self.width,self.height),interpolation=cv2.INTER_CUBIC)
        if t%15>=11.4:image=self._title(image,t%15-11.4)
        return image
    def _title(self,image,t):
        if t<.65:return image
        fade=min(1.,(t-.65)/.35);mask=self.mask*fade;h,w=mask.shape
        # Project the actual occluder mask away from the central light source.
        small=cv2.resize(mask,(max(1,w//4),max(1,h//4)));shadow=np.zeros_like(small);sh,sw=small.shape
        for k in range(1,13):
            scale=1+k*.018
            mat=cv2.getRotationMatrix2D((sw/2,sh/2),0,scale)
            shadow+=cv2.warpAffine(small,mat,(sw,sh),flags=cv2.INTER_LINEAR)*((13-k)/78)
        shadow=cv2.resize(shadow,(w,h));rgb=image.astype(np.float32)/255
        rgb*=1-.55*shadow[...,None]
        sweep=np.exp(-((np.arange(w)/w-(t*.28-.3))/.10)**2)[None,:]
        brushed=.65+.10*np.sin(np.arange(h)[:,None]*1.7)+.25*sweep
        metal=np.stack([brushed*.94,brushed*.91,brushed*.83],axis=-1)
        rgb=rgb*(1-mask[...,None])+metal*mask[...,None]
        # Screen-blend defocused background light onto the outer three-pixel rim.
        rim=np.maximum(0,cv2.dilate(mask,np.ones((7,7),np.uint8))-mask)
        wrapped=cv2.GaussianBlur(image,(0,0),8).astype(np.float32)/255
        rgb=1-(1-rgb)*(1-wrapped*rim[...,None]*.8)
        return np.uint8(np.clip(rgb*255,0,255))
