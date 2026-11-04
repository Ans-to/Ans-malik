#!/usr/bin/env python3
"""Render a 5-act documentary draft through the mandatory optical and audio buses."""
import os
os.environ.setdefault('NUMBA_NUM_THREADS', '2')
import argparse, asyncio, json, math, re, subprocess, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from forge_python.ffmpeg import get_ffmpeg_exe
from forge_python.audio_mastering.pedalboard_master import master
from forge_python.post_fx.optical_lens import finish_frame
from forge_python.render.compositor import SevenLayerCompositor
from forge_python.render.voice import OfflineVoice
from forge_python.render.document import ClassifiedDocument
from forge_python.render.hero import ThreeHero
from scipy.signal import resample

FPS=60

def script_for(topic):
    if not any(term in topic.lower() for term in (' ai', 'ai ', 'artificial intelligence', 'language model', 'chatgpt')):
        return [f'{topic}. Let us look closer.', 'Start by asking a clear question.', 'Look at the available evidence and the limits of the data.', 'Consider alternative explanations and check the context.', 'Verify important claims before drawing a conclusion.']
    return [f'{topic}. Let us look closer.',
            'A fluent answer can look convincing even when it is wrong.',
            'The system predicts likely patterns, not guaranteed facts.',
            'Gaps in context and uncertain evidence can shape the result.',
            'Ask for sources, check important claims, and think beyond the answer.']

async def synthesize(script, target):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(' '.join(script), 'en-US-ChristopherNeural').save(str(target)), timeout=20)

def prepare_audio(script,duration,tmp,whisper_model):
    sr=24000; n=int(duration*sr); speech=np.zeros(n,dtype=np.float32); words=[]; modes=[]
    offline=OfflineVoice(); model=None
    if whisper_model:
        try:
            from faster_whisper import WhisperModel
            model=WhisperModel(whisper_model,device='cpu',compute_type='int8',local_files_only=Path(whisper_model).exists())
        except Exception as exc: print(f'Whisper unavailable; using offline engine word events: {exc}', flush=True)
    for act,text in enumerate(script):
        voice=None; aligned=[]; mode='offline-espeak'
        if model is not None:
            try:
                mp3=tmp/f'voice-{act}.mp3'; wav=tmp/f'voice-{act}.wav'
                asyncio.run(synthesize([text],mp3))
                subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(mp3),'-ar',str(sr),'-ac','1',str(wav)],check=True)
                voice,_=sf.read(wav,dtype='float32')
                segments,_=model.transcribe(str(wav),word_timestamps=True)
                aligned=[{'word':item.word.strip(), 'start_ms':round(item.start*1000),'end_ms':round(item.end*1000)} for segment in segments for item in (segment.words or []) if item.word.strip()]
                def canonical(value): return re.findall(r'[^\W_]+',value.casefold(),flags=re.UNICODE)
                if canonical(text) != canonical(' '.join(item['word'] for item in aligned)):
                    raise ValueError('Whisper words differ from script; cannot guarantee alignment')
                mode='edge-tts+faster-whisper'
            except Exception as exc:
                print(f'Online voice/alignment failed for act {act+1}; using offline speech: {exc}',flush=True); voice=None
        if voice is None: voice,aligned=offline.speak(text,sr)
        act_start=round(act*duration/5*sr); act_end=round((act+1)*duration/5*sr)
        capacity=max(1,int((act_end-act_start)*.90)); scale=min(1.,capacity/len(voice))
        if scale<1: voice=resample(voice,capacity).astype(np.float32)
        offset=act_start+int((act_end-act_start-len(voice))/2)
        speech[offset:offset+len(voice)]+=voice
        for item in aligned:
            start=round(offset/sr*1000+item['start_ms']*scale); end=round(offset/sr*1000+item['end_ms']*scale)
            words.append({'word_id':len(words),'act':act,'word':item['word'],'start_ms':start,'end_ms':max(start+1,end),'source':mode})
        modes.append(mode)
    time=np.arange(n)/sr
    music=(0.016*np.sin(2*np.pi*55*time)+0.009*np.sin(2*np.pi*82.4*time)*(.65+.35*np.sin(2*np.pi*.13*time))).astype(np.float32)
    mix=master(music,speech,sr)
    path=tmp/'master.wav'; sf.write(path,mix,sr,subtype='FLOAT')
    return path, speech, sr, modes, words

def render(topic,duration,resolution,output,whisper_model=None):
    w,h=resolution
    if w<64 or h<64 or w%2 or h%2: raise ValueError('resolution must be even and at least 64x64')
    if duration<1: raise ValueError('duration must be at least one second')
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    script=script_for(topic)
    with tempfile.TemporaryDirectory(prefix='ceo-render-') as directory:
        tmp=Path(directory); audio,speech,sr,modes,words=prepare_audio(script,duration,tmp,whisper_model)
        doc=ClassifiedDocument([word for word in words if word['act']==1])
        Path(str(output)+'.brief.pdf').write_bytes(doc.pdf)
        hero=ThreeHero(w*2,h*2)
        compositor=SevenLayerCompositor(w,h,topic,words,doc,hero,finisher=finish_frame)
        metadata={'topic':topic,'acts':script,'voiceover_modes':modes,'word_timestamps':words,'document_word_boxes':doc.boxes,'fps':FPS,'resolution':[w,h], 'note':'Chart values are illustrative. Offline timing is from eSpeak word events.'}
        Path(str(output)+'.json').write_text(json.dumps(metadata,indent=2))
        command=[get_ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(FPS),'-i','-','-i',str(audio),'-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(output)]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            count=round(duration*FPS)
            for frame_idx in range(count):
                t=frame_idx/FPS; start=int(t*sr); samples=speech[start:min(len(speech),start+sr//FPS)]
                rms=float(np.sqrt(np.mean(samples**2))) if len(samples) else 0
                act=min(4,int(t/duration*5))
                progress=(t-duration*act/5)/(duration/5)
                # The compositor owns the finishing pass; no scene feeds the encoder directly.
                frame=compositor.compose(act,t,progress,rms,duration)
                proc.stdin.write(frame.tobytes())
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
    p.add_argument('--preview',action='store_true',help='Use 640x360 and at most 10 seconds for a quick draft'); p.add_argument('--topic',required=True); p.add_argument('--duration',type=float,default=60); p.add_argument('--resolution',type=resolution,default=(1920,1080)); p.add_argument('--output',default='final_video.mp4'); p.add_argument('--whisper-model',help='Path to a locally cached faster-whisper model (optional)')
    a=p.parse_args(); print('Rendered:',render(a.topic,min(a.duration,10) if a.preview else a.duration,(640,360) if a.preview else a.resolution,a.output,a.whisper_model))
if __name__=='__main__': main()
