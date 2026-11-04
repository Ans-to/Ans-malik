"""Continuous multi-plane world-space camera and procedural documentary objects.

The world uses a +Z forward camera, so closer planes have *smaller* Z values.
It projects persistent world-space artwork and connectors through one cubic
spline camera; visibility is determined by the frustum, not a scene switch.
"""
from dataclasses import dataclass
import math
import cv2
import numpy as np
from numba import njit, prange
from PIL import Image, ImageDraw
from scipy.interpolate import CubicSpline, PchipInterpolator
from forge_python.render.scenes import font, wrap

@dataclass(frozen=True)
class WorldNode:
    name: str
    position: tuple
    rotation: tuple = (0., 0., 0.)

@njit(parallel=True)
def velocity_blur(image, vx, vy, vz, taps=12):
    """Integrate a 180-degree shutter along projected pan and zoom velocities."""
    h,w,_=image.shape; out=np.empty_like(image)
    for y in prange(h):
        for x in range(w):
            # vz is a fraction of the frame per shutter interval.
            dx=vx+vz*(x-(w-1)*.5); dy=vy+vz*(y-(h-1)*.5)
            for ch in range(3):
                accum=0.
                for i in range(taps):
                    u=(i/(taps-1)-.5)
                    xx=max(0,min(w-1,int(round(x+u*dx))))
                    yy=max(0,min(h-1,int(round(y+u*dy))))
                    accum+=image[yy,xx,ch]
                out[y,x,ch]=np.uint8(accum/taps)
    return out

def rotation(pitch,yaw,roll):
    cp,sp=math.cos(pitch),math.sin(pitch);cy,sy=math.cos(yaw),math.sin(yaw);cr,sr=math.cos(roll),math.sin(roll)
    return np.array([[cr,-sr,0],[sr,cr,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cp,-sp],[0,sp,cp]])

class WorldEngine:
    def __init__(self, width, height, duration, topic, document, words, hero=None):
        if duration<=0: raise ValueError('duration must be positive')
        self.width,self.height,self.duration=width,height,duration
        self.topic,self.doc,self.words,self.hero=topic,document,words,hero
        self.nodes=[WorldNode(name,(i*1700., 80*math.sin(i*.8), i*230.),(0,0,0)) for i,name in enumerate(('THE QUESTION','THE RECORD','THE SIGNAL','THE NETWORK','THE TAKEAWAY'))]
        # A single position/orientation spline: holds are shallow arcs, never discontinuous.
        times=[]; values=[]
        for i,node in enumerate(self.nodes):
            center=np.array(node.position); visit=duration*i/5
            if i==0:
                times.append(0.);values.append([center[0]-80,center[1]+20,center[2]-1400,0.,-.02,0.])
            else:
                prev=np.array(self.nodes[i-1].position)
                for frac,blend in ((.25,.02),(.55,.07),(.72,.35),(.88,.84)):
                    tt=duration*(i-1+frac)/5
                    pos=prev*(1-blend)+center*blend
                    # Approach the foreground portal during travel; retreat before the next subject.
                    z=pos[2]-1400+480*math.sin(math.pi*blend)**2
                    times.append(tt);values.append([pos[0],pos[1]+45*math.sin(frac*math.pi),z,.035*math.sin(blend*math.pi),.26*math.sin(blend*math.pi),.025*math.sin(blend*math.pi)])
                times.append(visit);values.append([center[0],center[1],center[2]-1400,0.,-.02 if i%2==0 else .02,0.])
        last=np.array(self.nodes[-1].position)
        times.append(duration);values.append([last[0]+65,last[1]+20,last[2]-1370,.015,.01,.005])
        self.camera_path=CubicSpline(np.asarray(times),np.asarray(values),axis=0,bc_type='natural')
        self.curve=PchipInterpolator(np.linspace(0,1,9),[.18,.27,.23,.45,.37,.59,.55,.70,.84])
        rng=np.random.default_rng(84)
        self.stars=np.vstack([np.column_stack((node.position[0]+rng.uniform(-1100,1100,35), node.position[1]+rng.uniform(-700,700,35), np.full(35,node.position[2]-350),rng.uniform(1,3,35))) for node in self.nodes])
        card=Image.new('RGBA',(420,130),(21,38,52,215)); cd=ImageDraw.Draw(card,'RGBA')
        cd.rectangle((1,1,418,128),outline=(130,190,205,210),width=2)
        cd.text((22,35),'EVIDENCE / VERIFY',font=font('JetBrainsMono-Medium.ttf',25),fill=(235,235,225,255))
        self.evidence_card=np.asarray(card)

    def camera(self,t):
        t=np.clip(t,0,self.duration)
        return self.camera_path(t), self.camera_path(t,1)
    def project(self,points,t):
        pose,_=self.camera(t); points=np.atleast_2d(np.asarray(points,dtype=float))
        camera_points=(points-pose[:3]) @ rotation(*pose[3:])
        z=camera_points[:,2]; f=self.width*.75
        safe=np.where(np.abs(z)<1e-5,1e-5,z)
        return np.column_stack((self.width/2+camera_points[:,0]*f/safe,self.height/2-camera_points[:,1]*f/safe,z))
    def corners(self,node,t,z_offset=0,scale=1.,pitch_offset=0.):
        center=np.array(node.position)+np.array([0,0,z_offset]);a,b=550*scale,350*scale
        local=np.array([[-a,b,0],[a,b,0],[a,-b,0],[-a,-b,0]]) @ rotation(node.rotation[0]+pitch_offset,*node.rotation[1:]).T
        return self.project(local+center,t)
    def node_progress(self,index,t):
        # Event cascade starts while approaching the physical node, not at a cut.
        visit=self.duration*index/5
        return max(0., t-(visit-1.15 if index else 0.))
    def _texture(self,index,t,rms):
        w,h=1000,640;img=Image.new('RGBA',(w,h),(17,22,32,242));d=ImageDraw.Draw(img,'RGBA')
        d.rounded_rectangle((4,4,w-5,h-5),radius=15,outline=(122,180,195,170),width=3)
        d.text((45,35),f'FIELD NOTE  /  {index+1:02}  /  {self.nodes[index].name}',font=font('JetBrainsMono-Medium.ttf',21),fill=(6,182,212,255))
        d.line((45,78,955,78),fill=(150,182,192,125),width=2)
        local=self.node_progress(index,t)
        if index==0:
            f=font('Inter-ExtraBold.ttf',57); lines=wrap(d,self.topic,f,790)
            for i,line in enumerate(lines[:4]):d.text((48,125+i*68),line,font=f,fill=(243,244,246,255))
            d.text((48,510),'Trace the evidence.',font=font('InstrumentSerif-Italic.ttf',38),fill=(245,158,11,255))
            for i in range(4):d.arc((695-i*25,290-i*25,925+i*25,520+i*25),int((t*7)%360),int((t*7)%360)+260,fill=(6,182,212,100),width=2)
        elif index==1:
            paper=self.doc.paper.copy(); active=next((q for q in self.words if q['start_ms']<=t*1000<q['end_ms']),None)
            if active:
                box=next((b['box'] for b in self.doc.boxes if b['word_id']==active['word_id']),None)
                if box:
                    x0,y0,x1,y1=map(int,box);p=np.clip((t*1000-active['start_ms'])/max(1,active['end_ms']-active['start_ms']),0,1)
                    part=paper[y0:y1,x0:x0+int((x1-x0)*p)];part[:]=np.rint(part*(.45+.55*np.array([250,204,21])/255)).astype(np.uint8)
            page=Image.fromarray(paper).resize((360,466),Image.Resampling.LANCZOS);img.paste(page,(575,105)); d=ImageDraw.Draw(img,'RGBA')
            d.text((48,170),'THE\nRECORD',font=font('Inter-ExtraBold.ttf',64),fill=(243,244,246,255),spacing=3)
            d.text((50,380),'Read the fine print.',font=font('InstrumentSerif-Italic.ttf',37),fill=(245,158,11,255))
        elif index==2:
            d.text((50,110),'CONFIDENCE',font=font('Inter-ExtraBold.ttf',55),fill=(243,244,246,255))
            d.text((50,175),'is not truth.',font=font('InstrumentSerif-Italic.ttf',42),fill=(245,158,11,255))
            x0,y0,x1,y1=60,270,940,530
            for j in range(5): d.line((x0,y0+j*65,x1,y0+j*65),fill=(93,143,160,90),width=2)
            p=min(1.,max(.02,1-math.exp(-max(0.,local-.6)*.75)))
            xs=np.linspace(0,p,100);points=[(x0+x*(x1-x0),y1-float(self.curve(x))*(y1-y0)) for x in xs]
            d.polygon([(x0,y1),*points,(points[-1][0],y1)],fill=(6,120,150,65))
            d.line(points,fill=(64,215,232,250),width=4); x,y=points[-1];d.ellipse((x-9,y-9,x+9,y+9),outline=(245,158,11,255),width=3)
            d.text((730,115),f'{float(self.curve(p))*100:05.1f}',font=font('JetBrainsMono-Medium.ttf',34),fill=(245,158,11,255))
            d.text((50,566),'ILLUSTRATIVE INDEX / NOT MEASURED DATA',font=font('JetBrainsMono-Medium.ttf',18),fill=(190,210,218,190))
        elif index==3:
            d.text((48,116),'PATTERNS',font=font('Inter-ExtraBold.ttf',55),fill=(243,244,246,255))
            d.text((48,188),'are not proof.',font=font('InstrumentSerif-Italic.ttf',43),fill=(245,158,11,255))
            points=[]
            for i in range(160):
                a=i*2.399963+t*.24;z=1-2*(i+.5)/160;r=math.sqrt(1-z*z); X=r*math.cos(a);Y=r*math.sin(a);points.append((700+X*215/(1.8+z),340+Y*215/(1.8+z),z))
            for i,(x,y,z) in enumerate(points):
                for j in (i+13,i+21):
                    if j<len(points):d.line((x,y,points[j][0],points[j][1]),fill=(6,182,212,45),width=1)
            for x,y,z in sorted(points,key=lambda q:q[2]):
                r=2.2*(1.2+z*.4)*(1+min(1,rms*3));d.ellipse((x-r,y-r,x+r,y+r),fill=(105,210,224,210))
        else:
            d.text((48,145),'ASK.\nTHEN VERIFY.',font=font('Inter-ExtraBold.ttf',67),fill=(243,244,246,255),spacing=5)
            d.text((48,406),'A better question begins here.',font=font('InstrumentSerif-Italic.ttf',35),fill=(245,158,11,255))
            if self.hero:
                hero=Image.fromarray(self.hero.frame(round(t*60),60,''))
                region=hero.crop((500,100,1000,600)).resize((450,450),Image.Resampling.LANCZOS)
                img.paste(region,(520,100)); d=ImageDraw.Draw(img,'RGBA')
            else:
                x,y=760,330; d.polygon(((x,y-170),(x+125,y),(x,y+170),(x-125,y)),fill=(57,91,112,255),outline=(137,195,210,255));d.arc((x-190,y-70,x+190,y+70),0,345,fill=(245,158,11,230),width=3)
        # Four-beat build: draw wire first, then reveal, then rack focus.
        amount=.35+.65*np.clip(local/.6,0,1); wire=Image.new('RGBA',(w,h));wd=ImageDraw.Draw(wire,'RGBA')
        corners=[(4,4),(w-5,4),(w-5,h-5),(4,h-5),(4,4)]
        remaining=amount*4
        for k in range(4):
            progress=min(1,max(0,remaining-k)); a,b=corners[k],corners[k+1]
            if progress>0: wd.line((a[0],a[1],a[0]+(b[0]-a[0])*progress,a[1]+(b[1]-a[1])*progress),fill=(75,205,222,210),width=3)
        reveal=np.clip((local-.6)/.7,0,1);reveal=.18+.82*(1-(1-reveal)**3)
        rgba=np.asarray(img).copy();rgba[:,:,3]=(rgba[:,:,3].astype(float)*reveal).astype(np.uint8)
        rack=np.clip((local-1.3)/.8,0,1);rack=rack*rack*(3-2*rack)
        if rack>0:
            blurred=cv2.GaussianBlur(rgba,(0,0),1.4*rack+.01)
            rgba[:,:,:3]=(blurred[:,:,:3]*(1-.30*rack)).astype(np.uint8)
        return np.asarray(Image.alpha_composite(wire,Image.fromarray(rgba,'RGBA')))
    def _overlay(self,dest,texture,polygon):
        H,W=dest.shape[:2]; xy=polygon[:,:2]
        if np.any(polygon[:,2]<35) or not np.all(np.isfinite(xy)):return
        x0=max(0,int(np.floor(xy[:,0].min()))-2);y0=max(0,int(np.floor(xy[:,1].min()))-2)
        x1=min(W,int(np.ceil(xy[:,0].max()))+2);y1=min(H,int(np.ceil(xy[:,1].max()))+2)
        if x1<=x0 or y1<=y0:return
        th,tw=texture.shape[:2];src=np.float32([[0,0],[tw-1,0],[tw-1,th-1],[0,th-1]])
        mat=cv2.getPerspectiveTransform(src,(xy-np.array([x0,y0])).astype(np.float32))
        warped=cv2.warpPerspective(texture,mat,(x1-x0,y1-y0),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        region=dest[y0:y1,x0:x1]; alpha=warped[:,:,3:4].astype(np.float32)/255; inv=1-alpha
        # Straight-alpha over (destination starts transparent).
        dest_a=region[:,:,3:4].astype(np.float32)/255; out_a=alpha+dest_a*inv
        numerator=warped[:,:,:3].astype(np.float32)*alpha+region[:,:,:3].astype(np.float32)*dest_a*inv
        region[:,:,:3]=np.divide(numerator,np.maximum(out_a,1e-6)).astype(np.uint8);region[:,:,3]=np.rint(out_a[:,:,0]*255).astype(np.uint8)
    def render_layer(self,t,rms=0):
        W,H=self.width,self.height; layer=np.zeros((H,W,4),np.uint8)
        # Long 3D rails connect all persistent objects.
        for i in range(len(self.nodes)-1):
            a=np.array(self.nodes[i].position);b=np.array(self.nodes[i+1].position)
            us=np.linspace(0,1,90); rail=np.array([(1-u)**2*a+2*(1-u)*u*((a+b)/2+np.array([0,-350,100]))+u*u*b for u in us])
            projection=self.project(rail,t); good=projection[:,2]>35
            for j in range(len(rail)-1):
                if good[j] and good[j+1]:
                    p0,p1=projection[j,:2],projection[j+1,:2]
                    if np.max(np.abs([*p0,*p1]))<W*10: cv2.line(layer,tuple(p0.astype(int)),tuple(p1.astype(int)),(6,182,212,130),max(2,W//1500),cv2.LINE_AA)
        # Background architecture is at a farther plane, projected continuously.
        pose,_=self.camera(t);back_z=1500
        for k in range(-3,21):
            seg=np.array([[k*400,-1000,back_z],[k*400,1000,back_z]])
            q=self.project(seg,t)
            if np.all(q[:,2]>35):cv2.line(layer,tuple(q[0,:2].astype(int)),tuple(q[1,:2].astype(int)),(70,130,150,48),2,cv2.LINE_AA)
        # Hollow foreground gates are real fixed world planes, passed by the camera.
        for i in range(4):
            center=(np.array(self.nodes[i].position)+np.array(self.nodes[i+1].position))/2
            center[2]-=980
            portal=WorldNode('portal',tuple(center))
            q=self.corners(portal,t,scale=.78)
            if np.all(q[:,2]>35) and np.max(np.abs(q[:,:2]))<W*20:
                cv2.polylines(layer,[q[:,:2].astype(np.int32).reshape(-1,1,2)],True,(245,158,11,90),max(2,W//2000),cv2.LINE_AA)
        # Back-to-front painter ordering keeps all five nodes in the same world.
        for i in sorted(range(5),key=lambda j:self.project([self.nodes[j].position],t)[0,2],reverse=True):
            node=self.nodes[i]; local=self.node_progress(i,t); pitch=.20+(.785-.20)*math.exp(-local*3.5)
            corners=self.corners(node,t,pitch_offset=pitch)
            if np.any(corners[:,2]<35) or corners[:,0].max()<0 or corners[:,0].min()>W or corners[:,1].max()<0 or corners[:,1].min()>H:continue
            self._overlay(layer,self._texture(i,t,rms),corners)
            # Floating evidence plane moves separately from the main artifact.
            # A dim marker is always present on the floating plane; on beat 3
            # the evidence card springs forward, separating from the document.
            pop=max(0.,min(1.12,1-math.exp(-5*max(0,local-1.3))*math.cos(8*max(0,local-1.3))))
            card=self.evidence_card.copy()
            card[:,:,3]=(card[:,:,3].astype(np.float32)*(.16+.84*min(1.,pop))).astype(np.uint8)
            card_node=WorldNode('card',tuple(np.array(node.position)+np.array([250,-270,-150-180*pop])))
            self._overlay(layer,card,self.corners(card_node,t,scale=.32))
        # Foreground markers are fixed world points, so camera motion gives parallax.
        for x,y,z,r in self.stars:
            q=self.project([[x,y,z]],t)[0]
            if q[2]>35 and -20<q[0]<W+20 and -20<q[1]<H+20:
                rr=max(2,int(r*W/1920)); cv2.circle(layer,(int(q[0]),int(q[1])),rr,(150,205,220,80),-1,cv2.LINE_AA)
        return Image.fromarray(layer,'RGBA')
    def apply_blur(self,frame,t,fps=60):
        pose,velocity=self.camera(t); f=frame.shape[1]*.75; depth=1400.
        vx=float(np.clip((-velocity[0]*f/depth-velocity[4]*f)/(fps*2),-20,20));vy=float(np.clip((velocity[1]*f/depth+velocity[3]*f)/(fps*2),-20,20));vz=float(np.clip(velocity[2]/depth/(fps*2),-.035,.035))
        if abs(vx)+abs(vy)+abs(vz)*frame.shape[1] < .4:return frame
        return velocity_blur(frame,vx,vy,vz)
