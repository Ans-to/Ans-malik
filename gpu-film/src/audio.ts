/**
 * audio.ts — 60 s score at 120 BPM, synthesised, plus a 4-beat render.
 * Structure follows the shot list: 8 sections of 7.5 s, with a build into
 * each cut and a drop at 38 s (supply vs demand).
 */
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { synthesizeSoundtrack, writeWav } from '../../motion/src/audio/synth.ts';

const out = process.argv[2] ?? 'gpu-film/out/soundtrack.wav';
mkdirSync(dirname(out), { recursive: true });
// 8 bars x 2 loops = 60s at 120bpm; the synth builds 4-bar phrases, so run 4x
const track = synthesizeSoundtrack(120, 30);
writeWav(out, track);
console.log(`wrote ${out} ${track.duration.toFixed(2)}s`);
