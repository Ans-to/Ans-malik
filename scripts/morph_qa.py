"""Check the full motion output and sample one frame per compiled beat."""
import json,subprocess,sys
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe

def main():
    path=Path(sys.argv[1]);sheet=Path(sys.argv[2]);meta=json.loads(Path(str(path)+'.json').read_text())
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'])==(1920,1080)
    assert video['r_frame_rate']=='60/1' and int(video['nb_read_frames'])==meta['frames'],video
    assert video['pix_fmt']=='yuv420p' and abs(float(video['duration'])-meta['duration'])<.05
    assert meta['voice_mode']=='edge-tts+faster-whisper'
    assert len(meta['beats'])>=5 and all(3<=len(b['words'])<=4 for b in meta['beats'])
    assert sum(len(b['word_ids']) for b in meta['beats'])==len(meta['words'])
    frames=[min(meta['frames']-1,round((b['start']+(b['end']-b['start'])*.55)*60)) for b in meta['beats']]
    filt="select='"+'+'.join(f'eq(n,{n})' for n in frames)+"',scale=480:270,tile=3x"+str((len(frames)+2)//3)+":padding=8:margin=8:color=0x11131b"
    subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(path),'-vf',filt,'-frames:v','1',str(sheet)],check=True)
    print(f"QA OK: {meta['frames']} frames at 1080p60, {len(meta['beats'])} aligned beats, {audio['codec_name']} audio")
if __name__=='__main__':main()
