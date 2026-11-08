"""Verify exact output timing and generate a five-scene FFmpeg contact sheet."""
import json,subprocess,sys
from pathlib import Path
from forge_python.ffmpeg import get_ffmpeg_exe

def main():
    path=Path(sys.argv[1]);sheet=Path(sys.argv[2]);meta=json.loads(Path(str(path)+'.json').read_text())
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    print('QA details:', json.dumps({'video':video, 'format':probe['format'], 'voice_mode':meta.get('voice_mode'), 'word_timestamps':meta.get('word_timestamps')}), flush=True)
    assert (video['width'],video['height'])==(1920,1080),video
    assert video['r_frame_rate']=='60/1' and int(video['nb_read_frames'])==900,video
    assert video['pix_fmt']=='yuv420p' and abs(float(probe['format']['duration'])-15)<.05
    assert meta['voice_mode'].startswith('edge-tts') and meta['word_timestamps']
    assert any(12000<=w['start_ms']<15000 for w in meta['word_timestamps'])
    assert any(3000<=w['start_ms']<6000 and 'predict' in w['word'].lower() for w in meta['word_timestamps'])
    vf="select='eq(n,90)+eq(n,270)+eq(n,450)+eq(n,630)+eq(n,810)',scale=640:360,tile=2x3:padding=8:margin=8:color=0x11131b"
    subprocess.run([get_ffmpeg_exe(),'-v','error','-y','-i',str(path),'-vf',vf,'-frames:v','1',str(sheet)],check=True)
    print('QA OK: 1920x1080, 60fps, 900 frames, 15s, neural speech with word timings, audio:',audio['codec_name'])
if __name__=='__main__':main()
