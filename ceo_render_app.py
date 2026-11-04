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

FPS=60
MIN_SCENE_SECONDS=6.0
NARRATION_WPM=145
VOICE_GAP_SECONDS=0.6

def script_for(topic):
    if not any(term in topic.lower() for term in (' ai', 'ai ', 'artificial intelligence', 'language model', 'chatgpt')):
        return [f'{topic}. To understand the question, we need to look beyond the headline. The answer depends on context, evidence, and the assumptions we bring to the story.',
                'Start with a clear question and identify the sources behind the claims. A compelling account can leave out details that change how the evidence should be interpreted.',
                'Look at what the available evidence can and cannot tell us. An illustrative curve is not a measurement, and correlation alone does not establish a cause.',
                'Consider alternative explanations and ask what information is missing. A useful model can reveal patterns, but its conclusions still depend on the quality of its inputs.',
                'Before drawing a conclusion, check important claims against reliable sources. Keep uncertainty in view, and be ready to revise the story when better evidence appears.']
    return [f'{topic}. The answer can sound certain, detailed, and completely convincing. But fluent language is not the same thing as evidence, and a confident response can still be wrong.',
            'A fluent answer can look convincing even when it is wrong. These systems generate language by following learned patterns, so a polished explanation should not replace careful source checking.',
            'A language model predicts likely sequences from its context. The illustrative curve shows a changing score, not measured accuracy; probability is not a guarantee that a claim is true.',
            'Gaps in context, ambiguous questions, and unreliable source material can all shape an answer. The network finds patterns, but it does not automatically verify every fact it produces.',
            'Ask for sources, check important claims, and compare answers against reliable evidence. Use the model as a starting point, then apply judgment before making consequential decisions.']

async def synthesize(script, target):
    import edge_tts
    await asyncio.wait_for(edge_tts.Communicate(' '.join(script), 'en-US-ChristopherNeural', rate='-5%', pitch='-2Hz', boundary='WordBoundary').save(str(target), str(target)+'.jsonl'), timeout=45)

def prepare_audio(script, duration, tmp, whisper_model='base.en', require_online=False, offline=False):
    """Synthesize first, then extend the timeline to fit at the original speed.

    Every act has an equal duration of at least six seconds and sufficient room
    for its speech and an estimated 145-wpm reading. No speech is time-scaled.
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
    time=np.arange(n)/sr
    music=(0.016*np.sin(2*np.pi*55*time)+0.009*np.sin(2*np.pi*82.4*time)*(.65+.35*np.sin(2*np.pi*.13*time))).astype(np.float32)
    mix=master(music,speech,sr)
    path=tmp/'master.wav'; sf.write(path,mix,sr,subtype='FLOAT')
    return path, speech, sr, modes, words, actual_duration

def render(topic,duration,resolution,output,whisper_model="base.en",require_online=False,offline=False):
    w,h=resolution
    if w<64 or h<64 or w%2 or h%2: raise ValueError('resolution must be even and at least 64x64')
    if not math.isfinite(duration) or duration<=0: raise ValueError('duration must be finite and positive')
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    script=script_for(topic)
    with tempfile.TemporaryDirectory(prefix='ceo-render-') as directory:
        tmp=Path(directory); requested_duration=duration
        audio,speech,sr,modes,words,duration=prepare_audio(script,duration,tmp,whisper_model,require_online,offline)
        if duration>requested_duration: print(f'Extended duration from {requested_duration:g}s to {duration:g}s to preserve narration pace.',flush=True)
        doc=ClassifiedDocument([word for word in words if word['act']==1])
        Path(str(output)+'.brief.pdf').write_bytes(doc.pdf)
        hero=ThreeHero(w*2,h*2)
        compositor=SevenLayerCompositor(w,h,topic,words,doc,hero,finisher=finish_frame)
        metadata={'topic':topic,'acts':script,'voiceover_modes':modes,'word_timestamps':words,'document_word_boxes':doc.boxes,'fps':FPS,'resolution':[w,h],'requested_duration':requested_duration,'duration':duration, 'note':'Chart values are illustrative. Offline timing is from eSpeak word events.'}
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
    p.add_argument('--preview',action='store_true',help='Use 640x360 and at least 30 seconds for a paced draft'); p.add_argument('--topic',required=True); p.add_argument('--duration',type=float,default=60); p.add_argument('--resolution',type=resolution,default=(1920,1080)); p.add_argument('--output',default='final_video.mp4'); p.add_argument('--whisper-model',default='base.en',help='Faster-Whisper model name or local path (default: base.en)'); p.add_argument('--offline',action='store_true',help='Use offline eSpeak without an online probe'); p.add_argument('--require-online',action='store_true',help='Fail instead of using offline speech if Edge TTS or Whisper fails')
    a=p.parse_args(); print('Rendered:',render(a.topic,min(a.duration,30) if a.preview else a.duration,(640,360) if a.preview else a.resolution,a.output,a.whisper_model,a.require_online,a.offline))
if __name__=='__main__': main()
