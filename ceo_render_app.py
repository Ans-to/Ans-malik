#!/usr/bin/env python3
"""Render a 5-act documentary draft through the mandatory optical and audio buses."""
import os
os.environ.setdefault('NUMBA_NUM_THREADS', '2')
import argparse, asyncio, json, math, re, subprocess, tempfile, uuid
from pathlib import Path
import numpy as np
import soundfile as sf
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.audio_mastering.pedalboard_master import master
from forge_python.post_fx.optical_lens import finish_frame
from forge_python.render.voice import OfflineVoice
from forge_python.render.documentary_renderer import DocumentaryRenderer
from forge_python.render.documentary_timeline import make_timeline, active_shot, physical_transition, FPS as TIMELINE_FPS, KEYWORDS
from forge_python.render.impact_physics import ImpactPhysicsEngine, impact_music
import cv2

FPS=60
MIN_SCENE_SECONDS=6.0
NARRATION_WPM=190
VOICE_GAP_SECONDS=0.6

TRAILER_SCRIPT = "In 1971, Nixon closed the gold window. Foreign central banks lost gold conversion. Digital ledgers connect debt. In 2022, dollars were in eighty-eight percent of foreign exchange trades."

def script_for(topic):
    return [TRAILER_SCRIPT]  # The requested trailer is one naturally delivered act.

async def synthesize(script, target):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(' '.join(script), 'en-US-ChristopherNeural', rate='+12%', pitch='-2Hz', boundary='WordBoundary').save(str(target), str(target)+'.jsonl'), timeout=45)

def prepare_audio(script, duration, tmp, whisper_model='base.en', require_online=False, offline=False):
    """Synthesize first, then extend the timeline to fit at the original speed.

    Every act has an equal duration of at least six seconds and sufficient room
    for its speech and an estimated 190-wpm reading. No speech is time-scaled.
    """
    if not script or not math.isfinite(duration) or duration <= 0:
        raise ValueError('duration must be a finite positive number and script must not be empty')
    if offline and require_online: raise ValueError('offline and require_online are mutually exclusive')
    sr=24000; offline_voice=None; model=None; online_available=not offline
    clips=[]; modes=[]
    for act,text in enumerate(script):
        voice=None; aligned=[]; mode='offline-espeak'
        if online_available:
            try:
                mp3=tmp/f'voice-{act}.mp3'; wav=tmp/f'voice-{act}.wav'
                # Probe the actual TTS service; don't download a model when offline.
                asyncio.run(synthesize([text],mp3))
                subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(mp3),'-ar',str(sr),'-ac','1',str(wav)],check=True)
                voice,_=sf.read(wav,dtype='float32')
                if model is None:
                    from faster_whisper import WhisperModel
                    model=WhisperModel(whisper_model or 'base.en',device='cpu',compute_type='int8',local_files_only=Path(whisper_model or '').is_file() or (bool(whisper_model) and Path(whisper_model).is_dir()))
                segments,_=model.transcribe(str(wav),word_timestamps=True)
                aligned=[{'word':item.word.strip(), 'start_ms':round(item.start*1000),'end_ms':round(item.end*1000)} for segment in segments for item in (segment.words or []) if item.word.strip()]
                def canonical(value): return re.findall(r'[^\W_]+',value.casefold(),flags=re.UNICODE)
                if canonical(text) != canonical(' '.join(item['word'] for item in aligned)):
                    # Recognition can differ even with correct speech. Edge emits
                    # engine word boundaries alongside the actual synthesized audio.
                    boundary_file=Path(str(mp3)+'.jsonl')
                    if not boundary_file.exists(): raise ValueError('Whisper mismatch and Edge word boundaries are missing')
                    events=[json.loads(line) for line in boundary_file.read_text().splitlines() if line.strip()]
                    aligned=[{'word':e['text'], 'start_ms':round(e['offset']/10000), 'end_ms':round((e['offset']+e['duration'])/10000)} for e in events if e.get('type')=='WordBoundary']
                    if canonical(text) != canonical(' '.join(item['word'] for item in aligned)):
                        raise ValueError('Whisper and Edge word boundaries both differ from the script')
                    mode='edge-tts-boundaries+faster-whisper'
                else:
                    mode='edge-tts+faster-whisper'
                if not len(voice): raise ValueError('empty neural voiceover')
            except Exception as exc:
                if require_online: raise RuntimeError(f'Online voice/alignment failed for act {act+1}: {exc}') from exc
                print(f'Online voice/alignment unavailable; using offline speech: {exc}',flush=True)
                voice=None; online_available=False
        if voice is None:
            if offline_voice is None: offline_voice=OfflineVoice()
            voice,aligned=offline_voice.speak(text,sr)
        clips.append((voice,aligned)); modes.append(mode)
    required_scene=max([MIN_SCENE_SECONDS] + [max(len(voice)/sr+VOICE_GAP_SECONDS, len(re.findall(r"[^\W_]+", text, re.UNICODE))*60/NARRATION_WPM+VOICE_GAP_SECONDS) for text,(voice,_) in zip(script,clips)])
    frames_per_scene=math.ceil(max(duration/len(script),required_scene)*FPS)
    actual_duration=frames_per_scene*len(script)/FPS
    n=round(actual_duration*sr); speech=np.zeros(n,dtype=np.float32); words=[]
    for act,(voice,aligned) in enumerate(clips):
        act_start=round(act*frames_per_scene*sr/FPS); act_end=round((act+1)*frames_per_scene*sr/FPS)
        offset=act_start+(act_end-act_start-len(voice))//2
        if offset < act_start or offset+len(voice)>act_end: raise RuntimeError('narration does not fit in its scene')
        speech[offset:offset+len(voice)]+=voice
        for item in aligned:
            start=round(offset/sr*1000+item['start_ms']); end=round(offset/sr*1000+item['end_ms'])
            words.append({'word_id':len(words),'act':act,'word':item['word'],'start_ms':start,'end_ms':max(start+1,end),'source':modes[act]})
    shots,transitions=make_timeline(max(15., min(actual_duration,17.6)),words)
    impact_events=[x['frame']/FPS for x in transitions if x['frame']/FPS<actual_duration]
    music=impact_music(actual_duration,sr,words,events=[0.]+impact_events)
    mix=master(music,speech,sr)
    path=tmp/'master.wav'; sf.write(path,mix,sr,subtype='FLOAT')
    return path, speech, sr, modes, words, actual_duration

def render(topic,duration,resolution,output,whisper_model="base.en",require_online=False,offline=False,showcase=False):
    w,h=resolution
    if w<64 or h<64 or w%2 or h%2: raise ValueError('resolution must be even and at least 64x64')
    if not math.isfinite(duration) or duration<=0: raise ValueError('duration must be finite and positive')
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    script=script_for(topic)
    with tempfile.TemporaryDirectory(prefix='ceo-render-') as directory:
        tmp=Path(directory); requested_duration=duration
        audio,speech,sr,modes,words,duration=prepare_audio(script,duration,tmp,whisper_model,require_online,offline)
        if showcase and duration>15: raise ValueError(f'Narration needs {duration:.2f}s; shorten the script rather than speeding or truncating it')
        if duration>requested_duration: print(f'Extended duration from {requested_duration:g}s to {duration:g}s to preserve narration pace.',flush=True)
        hero=DocumentaryRenderer(w*2,h*2)
        cycle=max(15., min(duration,17.6))
        shots,transitions=make_timeline(cycle,words)
        event_times=[0.]+[x['frame']/FPS for x in transitions]
        physics=ImpactPhysicsEngine(w,h,duration,words,events=event_times)
        rng=np.random.default_rng(42)
        metadata={'topic':topic,'acts':script,'voiceover_modes':modes,'word_timestamps':words,'fps':FPS,'resolution':[w,h],'requested_duration':requested_duration,'duration':duration,'visual_engine':'11-shot Three.js documentary and physical transitions', 'shots':shots, 'transitions':transitions, 'shot_cycle_seconds':cycle, 'sources':['https://www.federalreservehistory.org/essays/gold-convertibility-ends','https://www.bis.org/press/p221027.htm'], 'showcase':showcase, 'note':'Offline timing is from eSpeak word events; offline voice is synthetic.'}
        Path(str(output)+'.json').write_text(json.dumps(metadata,indent=2))
        command=[get_ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(FPS),'-i','-','-i',str(audio),'-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(output)]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            count=round(duration*FPS)
            for frame_idx in range(count):
                t=frame_idx/FPS; f=frame_idx%round(cycle*FPS); shot_id=active_shot(shots,f)
                current=shots[shot_id]; local=(f-current['start_frame'])/FPS; length=(current['end_frame']-current['start_frame'])/FPS
                word=next((x for x in words if x['start_ms']<=t*1000<x['start_ms']+140 and any(token in KEYWORDS for token in re.findall(r'[a-z0-9]+',x['word'].lower()))),None)
                pulse=math.exp(-12*(t-word['start_ms']/1000)) if word else 0
                transition=next((x for x in transitions if x['frame']-x['duration_frames']//2<=f<x['frame']+x['duration_frames']//2),None)
                if transition:
                    end=transition['frame'];n=transition['duration_frames'];start=end-n//2;i=next(i for i,s in enumerate(shots) if s['start_frame']==end)
                    old=shots[i-1];new=shots[i]
                    left=hero.frame(i-1,max(0,(f-old['start_frame'])/FPS),(old['end_frame']-old['start_frame'])/FPS,pulse)
                    right=hero.frame(i,max(0,(f-new['start_frame'])/FPS),(new['end_frame']-new['start_frame'])/FPS,pulse)
                    left=cv2.resize(left,(w,h),interpolation=cv2.INTER_AREA);right=cv2.resize(right,(w,h),interpolation=cv2.INTER_AREA)
                    raw=physical_transition(left,right,(f-start)/(n-1),transition['kind'])
                else:
                    raw=cv2.resize(hero.frame(shot_id,local,length,pulse),(w,h),interpolation=cv2.INTER_AREA)
                graded=finish_frame(physics.transform(raw,t),rng)
                proc.stdin.write(graded.tobytes())
            proc.stdin.close(); code=proc.wait()
            if code: raise RuntimeError(f'ffmpeg failed ({code})')
        except BaseException:
            if proc.poll() is None: proc.kill()
            proc.wait(); output.unlink(missing_ok=True); raise
        finally:
            hero.close()
    return output

def resolution(value):
    try: return tuple(map(int,value.lower().split('x'))) if len(value.split('x'))==2 else (_ for _ in ()).throw(ValueError())
    except ValueError: raise argparse.ArgumentTypeError('expected WIDTHxHEIGHT')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--showcase',action='store_true',help='15-second documentary showcase with a short, naturally paced narration'); p.add_argument('--preview',action='store_true',help='Use 640x360 and at least 30 seconds for a paced draft'); p.add_argument('--topic',required=True); p.add_argument('--duration',type=float,default=60); p.add_argument('--resolution',type=resolution,default=(1920,1080)); p.add_argument('--output',default='final_video.mp4'); p.add_argument('--whisper-model',default='base.en',help='Faster-Whisper model name or local path (default: base.en)'); p.add_argument('--offline',action='store_true',help='Use offline eSpeak without an online probe'); p.add_argument('--require-online',action='store_true',help='Fail instead of using offline speech if Edge TTS or Whisper fails')
    a=p.parse_args(); duration=15 if a.showcase else (min(a.duration,30) if a.preview else a.duration); print('Rendered:',render(a.topic,duration,(640,360) if a.preview else a.resolution,a.output,a.whisper_model,a.require_online,a.offline,a.showcase))
if __name__=='__main__':
    try: main()
    except Exception as exc:
        if os.environ.get('GITHUB_ACTIONS'):
            message=str(exc).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
            print(f'::error title=Documentary render failed::{message}',flush=True)
        raise
