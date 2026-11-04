"""Finish every supplied video chunk before concatenating them with ffmpeg."""
import argparse
import subprocess
import tempfile
from pathlib import Path
from forge_python.post_fx.optical_lens import finish_video
from forge_python.ffmpeg import get_ffmpeg_exe

def assemble(chunks, output):
    if not chunks: raise ValueError('at least one chunk is required')
    if Path(output).resolve() in [Path(chunk).resolve() for chunk in chunks]:
        raise ValueError('output must differ from all inputs')
    with tempfile.TemporaryDirectory(prefix='cinema-forge-') as tmp:
        paths = []
        for index, chunk in enumerate(chunks):
            target = Path(tmp) / f'finished-{index:04}.mp4'
            finish_video(chunk, target, seed=index)
            paths.append(target)
        manifest = Path(tmp) / 'chunks.txt'
        manifest.write_text(''.join(f"file '{path.as_posix()}'\n" for path in paths))
        subprocess.run([get_ffmpeg_exe(), '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(manifest), '-c', 'copy', str(output)], check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True); parser.add_argument('chunks', nargs='+')
    args = parser.parse_args(); assemble(args.chunks, args.output)
if __name__ == '__main__': main()
