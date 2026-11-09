"""Synthesize independently and concatenate exact PCM sample windows.

These windows describe the decoded files, not acoustic phoneme boundaries. Edge
may include leading/trailing silence. No silence is trimmed and no time stretch
or resampling is performed after a clause is decoded to the common PCM format.
"""
import argparse
import asyncio
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from forge_python.ffmpeg import get_ffmpeg_exe

CLAUSES = [
    'In nineteen seventy-one,',
    'the United States quietly rewrote the rules of money.',
    'Physical gold walked right out of the vault,',
    'and high-speed digital ledgers took its place.',
    'Today, one currency still dominates the planet,',
    'powering eighty-eight percent of all global trade.',
]
SAMPLE_RATE = 48000
GAP_SAMPLES = SAMPLE_RATE * 180 // 1000
# Leave enough lead to inspect the pre-start frame of clause zero.
LEAD_SAMPLES = GAP_SAMPLES


def concatenate(paths, output, texts=CLAUSES, sample_rate=SAMPLE_RATE):
    if len(paths) != len(texts):
        raise ValueError('Expected one audio file per clause')
    gap = sample_rate * 180 // 1000
    lead = gap
    pieces = [np.zeros(lead, dtype=np.int16)]
    cursor = lead
    clauses = []
    for i, (path, text) in enumerate(zip(paths, texts)):
        audio, sr = sf.read(path, dtype='int16', always_2d=True)
        if sr != sample_rate or audio.shape[1] != 1 or not len(audio):
            raise ValueError(f'{path}: expected nonempty mono {sample_rate} Hz PCM')
        audio = audio[:, 0]
        start, end = cursor, cursor + len(audio)
        clauses.append(dict(clause_id=i, start_sample=start, end_sample=end,
                            start_sec=start / sr, end_sec=end / sr,
                            spoken_text=text))
        pieces.append(audio)
        cursor = end
        if i != len(paths)-1:
            pieces.append(np.zeros(gap, dtype=np.int16))
            cursor += gap
    samples = np.concatenate(pieces)
    sf.write(output, samples, sample_rate, subtype='PCM_16')
    return dict(sample_rate=sample_rate, gap_samples=gap, lead_samples=lead,
                total_samples=len(samples), clauses=clauses)


async def synthesize(outdir):
    import edge_tts
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, text in enumerate(CLAUSES):
        mp3 = outdir / f'clause_{i}.mp3'
        wav = outdir / f'clause_{i}.wav'
        await asyncio.wait_for(edge_tts.Communicate(text, 'en-US-AndrewNeural', rate='+0%').save(str(mp3)), timeout=90)
        subprocess.run([get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(mp3),
                        '-ar', str(SAMPLE_RATE), '-ac', '1', '-c:a', 'pcm_s16le', str(wav)], check=True)
        mp3.unlink()
        paths.append(wav)
    metadata = concatenate(paths, outdir / 'clauses.wav')
    (outdir / 'clauses.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='renders/clauses')
    args = parser.parse_args()
    asyncio.run(synthesize(Path(args.output_dir)))
