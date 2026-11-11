"""Natural neural narration, conservative pause capping, aligned beats and mix."""
import asyncio, math, re, subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.render.voice import OfflineVoice
from forge_python.audio_mastering.pedalboard_master import master, motion_foley, warm_vocal, limit_foley

SCRIPT=('In nineteen seventy one, the United States ended official dollar conversion into gold. '
        'Rules changed, but gold did not disappear. '
        'In twenty twenty two, the dollar appeared on one side of eighty eight percent of foreign exchange trades.')

def cap_long_pauses(samples, sr, threshold_db=-50, max_gap_ms=500, target_ms=280, fade_ms=5):
    """Cap only interior low-RMS gaps over 500ms; preserve all other samples.

    Cut from the centre of a long silent region so quiet consonant edges are not
    touched. A 5ms raised-cosine join is confined inside the low-RMS region.
    The returned map accounts for cuts and supports offline timing remapping.
    """
    x=np.asarray(samples,dtype=np.float32).reshape(-1);n=len(x);win=max(1,round(sr*.01))
    if not n:return x,lambda t:t
    levels=np.array([np.sqrt(np.mean(x[i:i+win].astype(np.float64)**2)) for i in range(0,n,win)])
    quiet=levels < 10**(threshold_db/20)
    edges=np.diff(np.r_[False,quiet,False].astype(np.int8));starts=np.where(edges==1)[0]*win;ends=np.minimum(np.where(edges==-1)[0]*win,n)
    target=round(target_ms*sr/1000);minimum=round(max_gap_ms*sr/1000);fade=round(fade_ms*sr/1000)
    cuts=[]
    for a,b in zip(starts,ends):
        if a==0 or b==n or b-a<=minimum:continue
        # The overlap removes fade samples too, leaving a target-length gap.
        keep=target+fade;cuts.append((int(a+keep//2),int(b-(keep-keep//2))))
    out=np.empty(0,np.float32);segments=[];cursor=0
    for a,b in cuts+[(n,n)]:
        part=x[cursor:a]
        if len(out) and len(part):
            f=min(fade,len(out),len(part));old=len(out);theta=np.linspace(0,np.pi/2,f)
            out[-f:]=out[-f:]*np.cos(theta)+part[:f]*np.sin(theta)
            segments.append((cursor,cursor+f,old-f,old));out=np.concatenate((out,part[f:]));segments.append((cursor+f,a,old,len(out)))
        else:
            begin=len(out);out=np.concatenate((out,part));segments.append((cursor,a,begin,len(out)))
        cursor=b
    def remap(seconds):
        sample=max(0,min(n,round(seconds*sr)))
        for a,b,c,d in segments:
            if a<=sample<=b:return (c+min(sample-a,d-c))/sr
        before=[seg for seg in segments if seg[1]<sample]
        return (before[-1][3] if before else 0)/sr
    return out,remap

def strip_dead_air(samples, sr):
    """Compress interior low-RMS runs longer than 70 ms to 35 ms.

    A 10 ms equal-power crossfade joins the retained parts. This aggressive
    energy heuristic can cut quiet consonants or intentional pauses; it is not
    a speech-aware edit. Leading and trailing silence are left untouched.
    """
    return cap_long_pauses(samples, sr, max_gap_ms=70, target_ms=35, fade_ms=10)

def canonical(text):
    """Compare common Whisper numeric spellings without treating them as errors."""
    text=text.casefold().replace('%',' percent ')
    text=re.sub(r'\b1971\b','nineteen seventy one',text)
    text=re.sub(r'\b2022\b','twenty twenty two',text)
    text=re.sub(r'\b88\b','eighty eight',text)
    return re.findall(r'[^\W_]+',text,flags=re.UNICODE)

def compile_beats(words,duration):
    """Keep spoken word order intact; distribute into groups of three or four."""
    count=len(words)
    if count<3:raise ValueError('At least three aligned words required')
    # Choose 3–4 word groups that best approach 1.15 s without inventing
    # timestamps or dropping words. Speech rate can make the target impossible.
    best={count:(0, [])}
    for i in range(count-1,-1,-1):
        choices=[]
        for size in (3,4):
            j=i+size
            if j>count or j not in best: continue
            start=0 if i==0 else words[i]['start_ms']/1000
            end=duration if j==count else words[j]['start_ms']/1000
            penalty=(end-start-1.15)**2 + best[j][0]
            choices.append((penalty,[size]+best[j][1]))
        if choices:best[i]=min(choices,key=lambda x:x[0])
    if 0 not in best:raise ValueError('Cannot partition words into 3–4 word groups')
    beats=[];i=0
    for b,size in enumerate(best[0][1]):
        chunk=words[i:i+size];start=0 if b==0 else chunk[0]['start_ms']/1000
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
    lead=round(.150*sr);tail=round(.400*sr)
    voice=np.pad(voice,(lead,tail))
    if mode=='offline-espeak':
        words=[{'word':w['word'],'start_ms':round((remap(w['start_ms']/1000)+.150)*1000),'end_ms':round((remap(w['end_ms']/1000)+.150)*1000)} for w in raw_words]
    else:
        wav=tmp/'trimmed.wav';sf.write(wav,voice,sr,subtype='FLOAT')
        from faster_whisper import WhisperModel
        whisper=WhisperModel(model,device='cpu',compute_type='int8',local_files_only=Path(model).exists())
        segments,_=whisper.transcribe(str(wav),word_timestamps=True)
        words=[{'word':w.word.strip(),'start_ms':round(w.start*1000),'end_ms':round(w.end*1000)} for seg in segments for w in (seg.words or []) if w.word.strip()]
        if canonical(SCRIPT)!=canonical(' '.join(w['word'] for w in words)):raise ValueError('Whisper transcript differs from narration; refusing inaccurate word lock')
    for i,w in enumerate(words):w.update(word_id=i,source=mode)
    duration=math.ceil(len(voice)/sr*60)/60;frames=round(duration*60)
    beats=compile_beats(words,duration)
    voice=np.pad(voice,(0,frames*sr//60-len(voice)))
    t=np.arange(len(voice))/sr; bed=(.009*np.sin(2*np.pi*110*t)+.006*np.sin(2*np.pi*165*t)).astype(np.float32)
    voice=warm_vocal(voice,sr)
    foley=limit_foley(motion_foley(duration,sr,beats,words),voice,below_db=18)
    mix=master(bed,voice,sr,sfx=foley,voice_presence=False)
    path=tmp/'master.wav';sf.write(path,mix,sr,subtype='FLOAT')
    return path,words,beats,mode,SCRIPT,frames
