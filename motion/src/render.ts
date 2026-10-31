/**
 * render.ts — the render pipeline.
 *
 *   frames (software raster + FX)  ->  PNG sequence  ->  ffmpeg -> H.264 + AAC
 *
 * Usage:
 *   node --experimental-strip-types motion/src/render.ts
 *   node --experimental-strip-types motion/src/render.ts --w=1920 --h=1080 --fps=30
 *   node --experimental-strip-types motion/src/render.ts --stills=1.2,3.4,6.2
 */

import { mkdirSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { encodePNG } from './core/png.ts';
import { analyzeAudio } from './audio/analyze.ts';
import { synthesizeSoundtrack, writeWav } from './audio/synth.ts';
import { Film, postProcess, glitchAmount, DURATION, type PostOptions } from './scene.ts';

const args = new Map<string, string>();
for (const a of process.argv.slice(2)) {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  if (m) args.set(m[1], m[2] ?? 'true');
}
const num = (k: string, d: number): number => (args.has(k) ? Number(args.get(k)) : d);

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const W = num('w', 1280);
const H = num('h', 720);
const FPS = num('fps', 30);
const OUT_DIR = resolve(ROOT, args.get('outdir') ?? 'motion/out');
const OUT_MP4 = resolve(ROOT, args.get('out') ?? 'motion/out/motion-by-code.mp4');
const AUDIO = join(OUT_DIR, 'soundtrack.wav');
const FRAMES = join(OUT_DIR, 'frames');
const CRF = num('crf', 20);
const POST: PostOptions = {
  bloom: num('bloom', 1.05),
  aberration: num('aberration', 1.4),
  grain: num('grain', 0.005),
};

mkdirSync(OUT_DIR, { recursive: true });

/* ------------------------------------------------------------------- audio */
if (!existsSync(AUDIO) || args.has('audio')) {
  const track = synthesizeSoundtrack(120, 4);
  writeWav(AUDIO, track);
  console.log(`[audio] synthesised ${AUDIO}`);
}
const analysis = analyzeAudio(AUDIO);
console.log(
  `[audio] ${analysis.bpm} BPM · ${analysis.beats.length} beats · ${analysis.onsets.length} onsets · ${analysis.duration.toFixed(2)}s`,
);

/* ------------------------------------------------------------------ frames */
const film = new Film({ w: W, h: H, analysis });
const rgb = new Uint8Array(W * H * 3);

function renderAt(t: number) {
  const raw = film.render(t);
  const out = postProcess(raw, t, glitchAmount(t), POST);
  out.toSRGB8(rgb);
  return encodePNG(rgb, W, H);
}

/* ------------------------------------------------------------------- stills */
if (args.has('stills')) {
  const dir = join(OUT_DIR, 'stills');
  mkdirSync(dir, { recursive: true });
  const times = (args.get('stills') || '')
    .split(',')
    .filter(Boolean)
    .map(Number);
  for (const t of times) {
    const t0 = performance.now();
    const png = renderAt(t);
    const file = join(dir, `still_${t.toFixed(2)}.png`);
    writeFileSync(file, png);
    console.log(`[still] t=${t.toFixed(2)}s -> ${file} (${(performance.now() - t0).toFixed(0)}ms)`);
  }
  process.exit(0);
}

/* ------------------------------------------------------------------- movie */
if (existsSync(FRAMES)) rmSync(FRAMES, { recursive: true, force: true });
mkdirSync(FRAMES, { recursive: true });

const total = Math.round(DURATION * FPS);
const start = performance.now();
for (let i = 0; i < total; i++) {
  const t = i / FPS;
  const png = renderAt(t);
  writeFileSync(join(FRAMES, `f_${String(i).padStart(4, '0')}.png`), png);
  if (i % 15 === 0 || i === total - 1) {
    const el = (performance.now() - start) / 1000;
    const eta = (el / (i + 1)) * (total - i - 1);
    process.stdout.write(
      `\r[render] frame ${i + 1}/${total}  ${(el / (i + 1) * 1000).toFixed(0)}ms/frame  eta ${eta.toFixed(0)}s   `,
    );
  }
}
process.stdout.write('\n');

/* ------------------------------------------------------------------- encode */
const ffmpeg = process.env.FFMPEG || join(ROOT, 'tools/ffmpeg');
mkdirSync(dirname(OUT_MP4), { recursive: true });
const ff = spawnSync(
  ffmpeg,
  [
    '-y',
    '-framerate', String(FPS),
    '-i', join(FRAMES, 'f_%04d.png'),
    '-i', AUDIO,
    '-c:v', 'libx264',
    '-preset', 'slow',
    '-crf', String(CRF),
    '-pix_fmt', 'yuv420p',
    '-profile:v', 'high',
    '-movflags', '+faststart',
    '-c:a', 'aac',
    '-b:a', '192k',
    '-shortest',
    OUT_MP4,
  ],
  { stdio: 'inherit' },
);
if (ff.status !== 0) {
  console.error('[encode] ffmpeg failed');
  process.exit(1);
}
// The PNG sequence is an intermediate: drop it unless explicitly kept.
if (!args.has('keep')) rmSync(FRAMES, { recursive: true, force: true });

const el = (performance.now() - start) / 1000;
console.log(`[done] ${OUT_MP4}  (${total} frames @ ${FPS}fps, ${el.toFixed(1)}s total)`);
