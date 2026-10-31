/**
 * build-audio.ts — synthesise the soundtrack, then measure it back.
 * Usage: node --experimental-strip-types motion/src/build-audio.ts [out.wav]
 */

import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { synthesizeSoundtrack, writeWav } from './audio/synth.ts';
import { analyzeAudio } from './audio/analyze.ts';

const out = process.argv[2] ?? 'motion/out/soundtrack.wav';
mkdirSync(dirname(out), { recursive: true });

const t0 = performance.now();
const track = synthesizeSoundtrack(120, 4);
writeWav(out, track);
const genMs = performance.now() - t0;

const a = analyzeAudio(out);
console.log(`wrote ${out}  ${track.duration.toFixed(2)}s  ${track.sampleRate}Hz  (synthesis ${genMs.toFixed(0)}ms)`);
console.log(`detected BPM: ${a.bpm}   beat: ${a.beat.toFixed(4)}s   beats: ${a.beats.length}`);
console.log(
  'beat times: ' +
    a.beats
      .slice(0, 16)
      .map((b) => b.t.toFixed(3))
      .join(' '),
);
console.log(`onsets: ${a.onsets.length}  (first 12: ${a.onsets.slice(0, 12).map((o) => o.t.toFixed(2)).join(', ')})`);
console.log(`peak punch @ 6.0s: ${a.punch(6.0).toFixed(3)}   rms@6.0: ${a.rmsAt(6).toFixed(3)}`);
