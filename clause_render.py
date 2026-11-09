"""Build a frame-quantized video from independently generated clause PCM."""
import argparse,json,math,subprocess
from pathlib import Path
from clause_audio import concatenate
from forge_python.ffmpeg import get_ffmpeg_exe

def main():
    p=argparse.ArgumentParser();p.add_argument('--audio-dir',default='assets/clause-voice');p.add_argument('--output',default='renders/final_video.mp4');p.add_argument('--resolution',default='1920x1080');p.add_argument('--samples');a=p.parse_args()
    src=Path(a.audio_dir);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    import soundfile as sf
    sr=sf.info(src/'clause_0.wav').samplerate
    wav=out.parent/'clause-mix.wav'
    meta=concatenate([src/f'clause_{i}.wav' for i in range(6)],wav,sample_rate=sr)
    meta.update(fps=60,frames=math.ceil(meta['total_samples']*60/sr),renderer='Chromium GSAP / per-clause PCM')
    data=out.parent/'clause-render-data.json';data.write_text(json.dumps(meta,indent=2))
    w,h=map(int,a.resolution.split('x'))
    cmd=['node','web/morph/render.mjs',f'data={data}',f'audio={wav}',f'ffmpeg={get_ffmpeg_exe()}',f'output={out}',f'width={w}',f'height={h}',f'frames={meta["frames"]}','clauses=1']
    if a.samples:cmd.append(f'samples={a.samples}')
    subprocess.run(cmd,check=True)
    if not a.samples:Path(str(out)+'.json').write_text(json.dumps(meta,indent=2))
if __name__=='__main__':main()
