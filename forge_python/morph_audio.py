"""Neural narration, silence stripping, word-aligned kinetic beats and mix."""
import asyncio, math, re, subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.render.voice import OfflineVoice
from forge_python.audio_mastering.pedalboard_master import master, motion_foley

SCRIPT=('AI can sound right. It predicts likely words, not verified facts. '
        'Follow the evidence, check the source, and compare claims before you trust an answer. '
        'Curiosity is your best filter. Even fluent answers need careful checking, every single time.')

def strip_dead_air(samples, sr, threshold_db=-40, min_gap_ms=70, target_ms=35, fade_ms=10):
    """Compress RMS-silent interior gaps and return samples plus old-to-new time map.

    A retained gap includes two equal-power joins: keep target + two overlap
    lengths before crossfading, so the resulting gap is approximately target.
    """
    x=np.asarray(samples,dtype=np.float32).reshape(-1); win=max(1,round(sr*.01)); n=len(x)
    if not n:return x,lambda t:t
    levels=np.array([np.sqrt(np.mean(x[i:i+win].astype(np.float64)**2)) for i in range(0,n,win)])
    silent=levels < 10**(threshold_db/20)
    edges=np.diff(np.r_[False,silent,False].astype(np.int8));starts=np.where(edges==1)[0]*win; ends=np.minimum(np.where(edges==-1)[0]*win,n)
    fade=round(fade_ms*sr/1000); target=round(target_ms*sr/1000); minimum=round(min_gap_ms*sr/1000)
    # Keep small regions at either edge of a long gap and crossfade their join.
    cuts=[]
    for a,b in zip(starts,ends):
        if b-a<=minimum:continue
        keep=target
        if a==0:cuts.append((0,max(0,b-round(.025*sr))))
        elif b==n:cuts.append((min(n,a+round(.025*sr)),n))
        elif b-a>keep+2*fade:
            cuts.append((int(a+(keep+fade)//2),int(b-(keep+fade-(keep+fade)//2))))
    result=np.empty(0,np.float32); segments=[]; cursor=0
    for a,b in cuts+[(n,n)]:
        part=x[cursor:a]
        if len(result) and len(part):
            f=min(fade,len(result),len(part)); old_len=len(result)
            theta=np.linspace(0,np.pi/2,f,endpoint=True)
            result[-f:]=result[-f:]*np.cos(theta)+part[:f]*np.sin(theta)
            segments.append((cursor,cursor+f,old_len-f,old_len))
            result=np.concatenate((result,part[f:]));segments.append((cursor+f,a,old_len,len(result)))
        else:
            start=len(result);result=np.concatenate((result,part));segments.append((cursor,a,start,len(result)))
        cursor=b
    def remap(seconds):
        i=max(0,min(n,round(seconds*sr)))
        for a,b,c,d in segments:
            if a<=i<=b:return (c+min(i-a,d-c))/sr
        before=[seg for seg in segments if seg[1]<i]
        return (before[-1][3] if before else 0)/sr
    return result,remap

def compile_beats(words,duration):
    """Keep spoken word order intact; distribute into groups of three or four."""
    count=len(words)
    if count<3:raise ValueError('At least three aligned words required')
    groups=math.ceil(count/4);base,extra=divmod(count,groups)
    if base<3:raise ValueError('Cannot partition words into 3–4 word groups')
    beats=[];i=0
    for b in range(groups):
        size=base+(b<extra);chunk=words[i:i+size];start=0 if b==0 else chunk[0]['start_ms']/1000
        beats.append({'index':b,'start':start,'words':[w['word'] for w in chunk],'word_ids':[w['word_id'] for w in chunk]});i+=size
    for i,beat in enumerate(beats):beat['end']=beats[i+1]['start'] if i+1<len(beats) else duration
    return beats

async def edge_voice(text,path):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(text,'en-US-AndrewNeural',rate='+12%',boundary='WordBoundary').save(str(path)),timeout=60)

def prepare(tmp,offline=False,require_online=False,model='base.en'):
    sr=24000; mode='edge-tts+faster-whisper'; voice=None
    if not offline:
        try:
            mp3=tmp/'voice.mp3';wav=tmp/'voice.wav';asyncio.run(edge_voice(SCRIPT,mp3))
            subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(mp3),'-ar',str(sr),'-ac','1',str(wav)],check=True)
            voice,_=sf.read(wav,dtype='float32')
        except Exception as e:
            if require_online:raise RuntimeError(f'Neural narration failed: {e}') from e
            print(f'Using offline voice: {e}',flush=True)
    if voice is None:
        voice,raw_words=OfflineVoice().speak(SCRIPT,sr);mode='offline-espeak'
    voice,remap=strip_dead_air(voice,sr)
    if mode=='offline-espeak':
        words=[{'word':w['word'],'start_ms':round(remap(w['start_ms']/1000)*1000),'end_ms':round(remap(w['end_ms']/1000)*1000)} for w in raw_words]
    else:
        wav=tmp/'trimmed.wav';sf.write(wav,voice,sr,subtype='FLOAT')
        from faster_whisper import WhisperModel
        whisper=WhisperModel(model,device='cpu',compute_type='int8',local_files_only=Path(model).exists())
        segments,_=whisper.transcribe(str(wav),word_timestamps=True)
        words=[{'word':w.word.strip(),'start_ms':round(w.start*1000),'end_ms':round(w.end*1000)} for seg in segments for w in (seg.words or []) if w.word.strip()]
        canonical=lambda s:re.findall(r'[^\W_]+',s.casefold(),flags=re.UNICODE)
        if canonical(SCRIPT)!=canonical(' '.join(w['word'] for w in words)):raise ValueError('Whisper transcript differs from narration; refusing inaccurate word lock')
    for i,w in enumerate(words):w.update(word_id=i,source=mode)
    duration=math.ceil((len(voice)/sr+.20)*60)/60;frames=round(duration*60)
    beats=compile_beats(words,duration)
    voice=np.pad(voice,(0,frames*sr//60-len(voice)))
    t=np.arange(len(voice))/sr; bed=(.009*np.sin(2*np.pi*110*t)+.006*np.sin(2*np.pi*165*t)).astype(np.float32)
    mix=master(bed,voice,sr,sfx=motion_foley(duration,sr,beats,words),voice_presence=True)
    path=tmp/'master.wav';sf.write(path,mix,sr,subtype='FLOAT')
    return path,words,beats,mode,SCRIPT,frames
