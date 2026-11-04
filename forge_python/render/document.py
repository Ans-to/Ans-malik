"""ReportLab classified brief, word boxes, and a perspective projection rig."""
import io
from pathlib import Path
import cv2
import pymupdf as fitz
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'shared_workspace/fonts/Inter-ExtraBold.ttf'
MONO=ROOT/'shared_workspace/fonts/JetBrainsMono-Medium.ttf'
pdfmetrics.registerFont(TTFont('ForgeInter',str(FONT)))
pdfmetrics.registerFont(TTFont('ForgeMono',str(MONO)))

class ClassifiedDocument:
    def __init__(self, words):
        """words: aligned word dicts for act two, in reading order."""
        buf=io.BytesIO(); pagew,pageh=612,792
        c=canvas.Canvas(buf,pagesize=(pagew,pageh)); c.setFillColorRGB(.94,.925,.90); c.rect(0,0,pagew,pageh,fill=1,stroke=0)
        c.setFillColorRGB(.09,.09,.10); c.setFont('ForgeMono',10); c.drawString(46,742,'FIELD NOTES / CLASSIFIED BRIEF'); c.setStrokeColorRGB(.72,.16,.14); c.setLineWidth(1.5);c.line(46,730,566,730)
        c.setFillColorRGB(.72,.16,.14);c.setFont('ForgeMono',9);c.drawString(46,705,'DOCUMENT 001  /  INTERNAL ANALYSIS')
        c.setFillColorRGB(.09,.09,.10);c.setFont('ForgeInter',19);c.drawString(46,665,'THE QUESTION OF TRUST')
        c.setFont('ForgeMono',8);c.drawString(46,636,'READING COPY  /  TIMED WORD ANNOTATIONS')
        c.setStrokeColorRGB(.55,.53,.50);c.line(306,220,306,610)
        # Decorative seal, classification strip and editorial micro-typography.
        c.setStrokeColorRGB(.65,.18,.16); c.circle(528,674,22,stroke=1,fill=0); c.circle(528,674,18,stroke=1,fill=0)
        c.setFillColorRGB(.65,.18,.16); c.setFont('ForgeMono',7); c.drawCentredString(528,672,'REVIEW')
        c.saveState(); c.translate(444,740); c.rotate(-7); c.setLineWidth(1.2); c.rect(0,0,111,18,stroke=1,fill=0); c.setFont('ForgeMono',10); c.drawString(8,4,'DECLASSIFIED'); c.restoreState()
        c.setFillColorRGB(.15,.15,.16); c.setFont('ForgeMono',7)
        filler = [
            'ANALYSIS NOTE / SOURCE MATERIAL',
            'Responses are generated from learned',
            'patterns and available context. A',
            'plausible formulation is not evidence.',
            'Cross-check names, figures and claims',
            'against reliable primary documents.',
            'Consider uncertainty before acting.',
            'Review the limits of each source.',
        ]
        for colx in (46,330):
            for j,line in enumerate(filler): c.drawString(colx,485-j*13,line)
            c.setFillColorRGB(.12,.12,.13); c.rect(colx,363,100,9,stroke=0,fill=1); c.rect(colx,346,72,9,stroke=0,fill=1)
            c.setFillColorRGB(.15,.15,.16)
        c.setFont('ForgeMono',7); c.drawString(46,310,'ASSESSMENT MATRIX / ILLUSTRATIVE')
        for row in range(4):
            yy=297-row*15; c.line(46,yy,566,yy)
            if row<3: c.drawString(50,yy-11,['CONTEXT','EVIDENCE','REVIEW'][row]);c.drawString(230,yy-11,['VARIABLE','REQUIRED','PENDING'][row]);c.drawString(420,yy-11,'[REDACTED]')
        boxes=[]; font='ForgeInter'; size=13; x=46.; y=588.; col=0; maxx=280.; lineheight=24.
        for index,item in enumerate(words):
            if col == 0 and index == (len(words)+1)//2 and len(words)>1:
                col=1; x=330; y=588; maxx=566
            word=item['word']; width=pdfmetrics.stringWidth(word,font,size); space=pdfmetrics.stringWidth(' ',font,size)
            if x+width>maxx and x> (46 if col==0 else 330): x=46 if col==0 else 330; y-=lineheight
            if y<220 and col==0: col=1;x=330;y=588;maxx=566
            if y<220: raise ValueError('Too much narration for classified document')
            c.setFont(font,size);c.drawString(x,y,word)
            # PDF y is bottom-up; raster coordinates are top-down and 2x.
            boxes.append({'word_id':item['word_id'],'word':word,'box':[x*2,(pageh-y-size*.95)*2,(x+width)*2,(pageh-y+size*.25)*2]})
            x+=width+space
        c.setFont('ForgeMono',8);c.setFillColorRGB(.72,.16,.14);c.drawString(46,106,'DECLASSIFIED FOR REVIEW  /  SOURCE CHECK REQUIRED')
        c.save();self.pdf=buf.getvalue();self.boxes=boxes
        pdf=fitz.open(stream=self.pdf,filetype='pdf'); pix=pdf[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
        self.paper=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3).copy();pdf.close()
        grain=np.random.default_rng(7).normal(0,1.5,self.paper.shape[:2])[...,None]
        self.paper=np.clip(self.paper.astype(np.float32)+grain,0,255).astype(np.uint8)

    def frame(self,w,h,t,words, transparent=False):
        active=next((item for item in words if item['start_ms']<=t*1000<item['end_ms']),None)
        image=self.paper.copy(); focus=np.array([image.shape[1]/2,image.shape[0]/2],dtype=float)
        if active:
            box=next((item['box'] for item in self.boxes if item['word_id']==active['word_id']),None)
            if box:
                x0,y0,x1,y1=map(int,box); frac=np.clip((t*1000-active['start_ms'])/max(1,active['end_ms']-active['start_ms']),0,1); end=x0+int((x1-x0)*frac)
                region=image[y0:y1,x0:end]; color=np.array([250,204,21],np.float32)/255
                region[:]=np.rint(region.astype(np.float32)*(.45+.55*color)).astype(np.uint8)
                focus=np.array([(x0+x1)/2,(y0+y1)/2])
        # 3D orientation and projection of the four corners, then homography.
        ph,pw=image.shape[:2]; pitch=.10+0.025*np.sin(t*.43); yaw=-.16+0.035*np.sin(t*.31); roll=.025*np.sin(t*.27)
        Rx=np.array([[1,0,0],[0,np.cos(pitch),-np.sin(pitch)],[0,np.sin(pitch),np.cos(pitch)]])
        Ry=np.array([[np.cos(yaw),0,np.sin(yaw)],[0,1,0],[-np.sin(yaw),0,np.cos(yaw)]])
        Rz=np.array([[np.cos(roll),-np.sin(roll),0],[np.sin(roll),np.cos(roll),0],[0,0,1]])
        rotation=Rz@Ry@Rx; corners=np.array([[-.5,-ph/pw/2,0],[.5,-ph/pw/2,0],[.5,ph/pw/2,0],[-.5,ph/pw/2,0]])@rotation.T
        # Smooth periodic push plus small tracking towards the active line.
        z=2.8-.12*np.sin(t*.4); focal=h*1.75; shift=(focus/np.array([pw,ph])-.5)*np.array([w*.18,h*.15])
        projected=np.column_stack((w*.70 + focal*corners[:,0]/(z+corners[:,2])-shift[0],h*.51+focal*corners[:,1]/(z+corners[:,2])-shift[1])).astype(np.float32)
        source=np.array([[0,0],[pw-1,0],[pw-1,ph-1],[0,ph-1]],np.float32)
        mat=cv2.getPerspectiveTransform(source,projected); warped=cv2.warpPerspective(image,mat,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(18,22,32))
        # Subtle depth blur at frame edges, leaving the central reading plane sharp.
        blurred=cv2.GaussianBlur(warped,(0,0),max(1,w/700)); yy,xx=np.ogrid[:h,:w]; dist=((xx-w/2)/(w/2))**2+((yy-h/2)/(h/2))**2
        alpha=np.clip((dist-.25)*.32,0,.42).astype(np.float32)[...,None]
        result=np.rint(warped*(1-alpha)+blurred*alpha).astype(np.uint8)
        if transparent:
            mask=cv2.warpPerspective(np.full((ph,pw),255,np.uint8),mat,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
            return np.dstack((result,mask))
        return result
