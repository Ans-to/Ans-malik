"""Per-beat Edge TTS, sample-counted concatenation and word-event timeline."""
import asyncio,json,math,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from storyboard_compiler import canonical
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.audio_mastering.pedalboard_master import master,warm_vocal,limit_foley
SR=48000
GAP=round(.18*SR)

async def edge_clips(plan,directory):
    import edge_tts
    directory.mkdir(parents=True,exist_ok=True)
    paths=[];events=[]
    for i,beat in enumerate(plan['beats']):
        mp3=directory/f'beat_{i}.mp3';wav=directory/f'beat_{i}.wav';ev=directory/f'beat_{i}.jsonl'
        await asyncio.wait_for(edge_tts.Communicate(beat['spoken_text'],'en-US-AndrewNeural',rate='+0%',boundary='WordBoundary').save(str(mp3),str(ev)),timeout=120)
        subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(mp3),'-ac','1','-ar',str(SR),'-c:a','pcm_s16le',str(wav)],check=True)
        paths.append(wav);events.append([json.loads(x) for x in ev.read_text().splitlines() if x.strip()]);mp3.unlink()
    return paths,events


def compile_timeline(plan,paths,events,sample_rate=SR,gap=None):
    if gap is None:gap=round(.18*sample_rate)
    if len(paths)!=len(plan['beats']) or len(events)!=len(paths):raise ValueError('Missing audio or word events')
    clips=[]
    for i,path in enumerate(paths):
        audio,sr=sf.read(path,dtype='float32',always_2d=True)
        if sr!=sample_rate or audio.shape[1]!=1 or len(audio)==0:raise ValueError(f'Beat {i}: nonempty mono PCM at {sample_rate}Hz required')
        clips.append(audio[:,0])
    # Retain every spoken sample at natural speed. Fill a longer requested
    # duration with explicit silence distributed between beats and at the tail.
    minimum=gap+sum(map(len,clips))+gap*max(0,len(clips)-1)
    target=math.ceil(plan['requested_duration']*60)*sample_rate//60
    extra=max(0,target-minimum);base,rem=divmod(extra,len(clips))
    pauses=[(gap if i<len(clips)-1 else 0)+base+(i<rem) for i in range(len(clips))]
    parts=[np.zeros(gap,dtype=np.float32)];cursor=gap;beats=[]
    for i,(b,audio,evs) in enumerate(zip(plan['beats'],clips,events)):
        matches=[e for e in evs if e.get('type')=='WordBoundary' and canonical(e.get('text',''))==canonical(b['trigger_word'])]
        if len(matches)!=1:raise ValueError(f'Beat {i}: expected exactly one WordBoundary for {b["trigger_word"]!r}, got {len(matches)}')
        e=matches[0];offset=int(e['offset']);offset_sample=round(offset*sample_rate/10_000_000)
        if not 0<=offset_sample<len(audio):raise ValueError(f'Beat {i}: word boundary outside decoded PCM')
        start=cursor;end=start+len(audio);trigger=start+offset_sample
        beats.append({**b,'index':i,'start_sample':start,'end_sample':end,'trigger_sample':trigger,'beat_start_ms':start*1000/sample_rate,'beat_end_ms':end*1000/sample_rate,'trigger_word_ms':trigger*1000/sample_rate,'trigger_frame':math.ceil(trigger*60/sample_rate),'word_event_offset_100ns':offset})
        parts.append(audio);parts.append(np.zeros(pauses[i],dtype=np.float32));cursor=end+pauses[i]
    speech=np.concatenate(parts);frames=math.ceil(len(speech)*60/sample_rate)
    return speech,{'topic':plan['topic'],'requested_duration':plan['requested_duration'],'sample_rate':sample_rate,'total_samples':len(speech),'minimum_gap_samples':gap,'post_beat_silence_samples':pauses,'fps':60,'frames':frames,'beats':beats,'timing_source':'Edge WordBoundary offsets quantized to PCM sample; not independently measured phoneme onsets','duration_policy':'Silence fills requested duration; longer speech extends output without speeding or truncation.'}


def write_master(speech,timeline,path):
    sr=timeline['sample_rate'];duration=len(speech)/sr
    voice=warm_vocal(speech,sr);foley=np.zeros((len(speech),2),np.float32)
    for b in timeline['beats']:
        at=b['trigger_sample'];n=min(round(.18*sr),len(speech)-at)
        if n>0:
            t=np.arange(n)/sr;click=np.sin(2*np.pi*(600*t-350*t*t))*np.exp(-30*t)*.07
            foley[at:at+n,0]+=click;foley[at:at+n,1]+=click
    foley=limit_foley(foley,voice,below_db=18)
    mix=master(np.zeros_like(voice),voice,sr,sfx=foley)
    sf.write(path,mix,sr,subtype='PCM_16')
    import pyloudnorm as pyln
    timeline['measured_lufs']=float(pyln.Meter(sr).integrated_loudness(mix))
    timeline['foley_policy']='At each Edge word event; whole-program RMS at least 18 dB below voice before mastering.'
    timeline['encoded_audio_note']='AAC encoding is lossy and may introduce priming; event timestamps do not certify acoustic onsets.'
