"""Narration, word alignment, ReportLab paper and light UI sound design."""
import asyncio,json,math,re,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter,sosfilt
from reportlab.pdfgen import canvas
import fitz
from forge_python.audio_mastering.pedalboard_master import master
from forge_python.render.voice import OfflineVoice
from forge_python.ffmpeg import get_ffmpeg_exe

AI_SEGMENTS=['AI can be wrong.','It predicts words.','Answers follow patterns.','Confidence is not evidence.','Check the source.']

async def edge_voice(text,path):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(text,'en-US-ChristopherNeural',rate='+0%',boundary='WordBoundary').save(str(path),str(path)+'.jsonl'),timeout=45)

def prepare_narration(topic,duration,tmp,offline=False,require_online=False,whisper_model='base.en'):
    if offline and require_online:raise ValueError('offline and require_online are incompatible')
    if not re.search(r'\bai\b|artificial intelligence|chatgpt|language model',topic.lower()):
        raise ValueError('This editorial composition currently supports the AI explainer only.')
    sr=24000;speech=np.zeros(round(duration*sr),np.float32);word_events=[];mode='edge-tts+faster-whisper'
    for i,text in enumerate(AI_SEGMENTS):
        voice=None;words=[]
        if not offline:
            try:
                mp3=tmp/f'voice-{i}.mp3';wav=tmp/f'voice-{i}.wav';asyncio.run(edge_voice(text,mp3))
                subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(mp3),'-ar',str(sr),'-ac','1',str(wav)],check=True)
                voice,_=sf.read(wav,dtype='float32')
                events=[json.loads(x) for x in Path(str(mp3)+'.jsonl').read_text().splitlines() if x.strip()]
                words=[{'word':e['text'],'start_ms':round(e['offset']/10000),'end_ms':round((e['offset']+e['duration'])/10000)} for e in events if e.get('type')=='WordBoundary']
            except Exception as e:
                if require_online:raise RuntimeError(f'Neural speech unavailable: {e}') from e
                print(f'Neural speech unavailable; using offline eSpeak: {e}',flush=True);voice=None
        if voice is None:
            voice,words=OfflineVoice().speak(text,sr);mode='offline-espeak'
        if len(voice)>round(2.95*sr):raise ValueError(f'Scene {i+1} narration is {len(voice)/sr:.2f}s, exceeds its 3-second scene')
        offset=round((i*3+(3-len(voice)/sr)/2)*sr);speech[offset:offset+len(voice)]=voice
        word_events.extend([{'word':w['word'],'start_ms':round(w['start_ms']+offset/sr*1000),'end_ms':round(w['end_ms']+offset/sr*1000)} for w in words])
    canonical=lambda s:re.findall(r'[^\W_]+',s.casefold(),flags=re.UNICODE)
    text=' '.join(AI_SEGMENTS)
    if mode!='offline-espeak':
        wav=tmp/'aligned-voice.wav';sf.write(wav,speech,sr)
        try:
            from faster_whisper import WhisperModel
            model=WhisperModel(whisper_model,device='cpu',compute_type='int8',local_files_only=Path(whisper_model).exists())
            segments,_=model.transcribe(str(wav),word_timestamps=True)
            whispered=[{'word':w.word.strip(),'start_ms':round(w.start*1000),'end_ms':round(w.end*1000)} for seg in segments for w in (seg.words or []) if w.word.strip()]
            if canonical(text)==canonical(' '.join(x['word'] for x in whispered)):word_events=whispered
            else:mode='edge-tts-boundaries+faster-whisper'
        except Exception:
            if require_online:raise
            mode='edge-tts-boundaries'
    if canonical(text)!=canonical(' '.join(x['word'] for x in word_events)):raise ValueError('Timed words do not match narration')
    aligned=[dict(w,word_id=i,source=mode) for i,w in enumerate(word_events)]
    return speech,sr,aligned,mode,text

def create_document(topic,path):
    """ReportLab PDF rendered to PNG, with phrase box for the SVG overlay."""
    pdf=path.with_suffix('.pdf');c=canvas.Canvas(str(pdf),pagesize=(760,980))
    c.setFillColorRGB(.98,.965,.93);c.rect(0,0,760,980,fill=1,stroke=0)
    c.setFillColorRGB(.28,.25,.28);c.setFont('Helvetica',18);c.drawString(78,900,'SOURCE NOTES  /  RESEARCH COPY')
    c.setStrokeColorRGB(.67,.63,.60);c.line(78,875,682,875)
    c.setFillColorRGB(.1,.09,.11);c.setFont('Helvetica-Bold',48);c.drawString(78,792,'A closer look')
    c.setFont('Helvetica',26);c.setFillColorRGB(.25,.23,.25)
    lines=['Fluency can create an illusion of certainty.', 'The answer may sound convincing even', 'when the underlying evidence is missing.', '', 'It predicts words.', '', 'Check the source behind the claim.', 'Look for context, dates and limitations.', 'Compare important information with', 'reliable independent evidence.']
    for i,line in enumerate(lines):c.drawString(78,720-i*38,line)
    c.setFont('Helvetica',18);c.drawString(78,150,'EDITORIAL BRIEF  /  ILLUSTRATIVE EXAMPLE');c.showPage();c.save()
    doc=fitz.open(str(pdf));pix=doc[0].get_pixmap(alpha=False);pix.save(str(path));doc.close()
    # Highlight targets the "It predicts..." line, in 760x980 image coordinates.
    return pdf,{'x1':78,'x2':560,'y':980-(720-4*38)-10}

def ui_score(duration,sr,words):
    n=round(duration*sr);t=np.arange(n)/sr;rng=np.random.default_rng(403)
    bed=(.012*np.sin(2*np.pi*110*t)+.009*np.sin(2*np.pi*164.8*t)+.006*np.sin(2*np.pi*220*t))*(.7+.3*np.cos(t*.32))
    sfx=np.zeros((n,2),np.float32)
    def add(at,sound,pan=.5):
        i=round(at*sr);k=min(len(sound),n-i)
        if i<0 or k<=0:return
        sfx[i:i+k,0]+=sound[:k]*(1-pan*.5);sfx[i:i+k,1]+=sound[:k]*(.5+pan*.5)
    # Small synthetic UI pops, paper slides, soft marker and lowpassed whooshes.
    for at in (.25,1.05,1.18,1.31,6.1,6.32,6.54,9.05,9.21,9.37,12.1):
        q=np.arange(int(.12*sr))/sr;pop=(np.sin(2*np.pi*(690*q-110*q*q))*np.exp(-q*35)*.07 + rng.standard_normal(len(q))*np.exp(-q*90)*.012);add(at,pop,at%1)
    for at in (3.08,3.23,3.38):
        q=np.arange(int(.38*sr))/sr;noise=sosfilt(butter(2,[650,4500],fs=sr,btype='bandpass',output='sos'),rng.standard_normal(len(q)));add(at,noise*np.sin(np.pi*q/.38)**2*.025,at%1)
    mark=next((w['start_ms']/1000 for w in words if 'predict' in w['word'].lower()),4.4);mark=max(3.0,min(5.2,mark))
    q=np.arange(int(.65*sr))/sr;noise=sosfilt(butter(2,[500,3000],fs=sr,btype='bandpass',output='sos'),rng.standard_normal(len(q)));add(mark,noise*np.sin(np.pi*q/.65)**2*.024,.4)
    for at in (3.,6.,9.,12.):
        q=np.arange(int(.42*sr))/sr;noise=sosfilt(butter(2,1200,fs=sr,output='sos'),rng.standard_normal(len(q)));add(at,noise*np.sin(np.pi*q/.42)**2*.022,.6)
    return bed.astype(np.float32),sfx

def make_audio(topic,duration,tmp,offline=False,require_online=False,whisper_model='base.en'):
    speech,sr,words,mode,text=prepare_narration(topic,duration,tmp,offline,require_online,whisper_model)
    music,sfx=ui_score(duration,sr,words);mix=master(music,speech,sr,sfx=sfx,voice_presence=True)
    path=tmp/'master.wav';sf.write(path,mix,sr,subtype='FLOAT');return path,words,mode,text
