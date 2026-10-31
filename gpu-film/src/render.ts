/**
 * render.ts — the GPU Price Explainer render pipeline.
 *
 * 60 s at 120 BPM. Frame-exact, resumable, aspect-aware, deterministic.
 *
 *   npm run draft           960x540  pass 1
 *   npm run review         1080x1920? no — 1920x1080 pass 3
 *   npm run final          3840x2160 pass 4
 *   npm run vertical       1080x1920 delivery
 */

import { mkdirSync, writeFileSync, existsSync, rmSync, readFileSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { encodePNG } from '../../motion/src/core/png.ts';
import * as FX from '../../motion/src/core/fx.ts';
import { Film, DURATION, SHOTS } from './scenes.ts';
import { loadCurves, measuredGoldenCurves, saveCurves, curveSVG } from './refcurve.ts';
import { slideshowGate, freezeGate, scoreSequence, transitionAudit, audioGate } from './gates.ts';
import { applyTransition, EDL } from './transitions.ts';

const args = new Map<string, string>();
for (const a of process.argv.slice(2)) {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  if (m) args.set(m[1], m[2] ?? 'true');
}
const num = (k: string, d: number): number => (args.has(k) ? Number(args.get(k)) : d);

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const GF = join(ROOT, 'gpu-film');
const OUT = join(GF, 'out');
const LOGS = join(GF, 'logs');
mkdirSync(OUT, { recursive: true });
mkdirSync(LOGS, { recursive: true });

const W = num('w', 960);
const H = num('h', 540);
const FPS = num('fps', 60);
const CRF = num('crf', 21);
const TAG = args.get('tag') ?? `${W}x${H}`;
const PASS = num('pass', 1);
const FRAME_DIR = join(OUT, `frames_${TAG}`);
const MP4 = resolve(ROOT, args.get('out') ?? `gpu-film/out/explainer_${TAG}.mp4`);
const AUDIO = join(OUT, 'soundtrack.wav');
const START = num('start', 0);
const END = num('end', DURATION);

/* ------------------------------------------------------------------ curves */
const curveDir = join(GF, 'assets', 'curves');
if (!existsSync(join(curveDir, 'dolly_in.json'))) {
  saveCurves(curveDir, measuredGoldenCurves());
  writeFileSync(join(LOGS, 'motion_curves.svg'), curveSVG(measuredGoldenCurves()));
}
const curves = loadCurves(curveDir);

/* ------------------------------------------------------------------ render */
const film = new Film({ w: W, h: H, curves });
const rgb = new Uint8Array(W * H * 3);
const t0 = performance.now();

/**
 * scrim — a soft left-side falloff so display type keeps its contrast against
 * the product. Not a vignette: it is directional, and it never touches the
 * right-hand third where the subject lives.
 */
function scrim(f: Frame): void {
  const { w, h, data } = f;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const gx = x / w;
      const gy = y / h;
      const k = 1 - 0.55 * Math.max(0, 1 - gx / 0.62) * Math.max(0, 1 - Math.abs(gy - 0.32) / 0.75);
      const o = (y * w + x) * 3;
      data[o] *= k;
      data[o + 1] *= k;
      data[o + 2] *= k;
    }
  }
}

/**
 * Composite the graphics pass over the graded 3D pass.
 * Additive, because every element of the type layer is light on a dark ground,
 * and because it keeps the type at exactly the contrast it was drawn with.
 * Type must never go through bloom: a halo around a glyph is the difference
 * between "printed" and "screenshot of a glow filter".
 */
function compositeType(base: Frame, gfx: Frame, ss: number): void {
  const d = base.data;
  const g = gfx.data;
  if (ss === 1) {
    for (let i = 0; i < d.length; i++) d[i] += g[i];
    return;
  }
  // box-filter the supersampled type layer down to the output grid
  const gw = gfx.w;
  const inv = 1 / (ss * ss);
  let i = 0;
  for (let y = 0; y < base.h; y++) {
    const row0 = y * ss;
    for (let x = 0; x < base.w; x++) {
      const col0 = x * ss;
      let r = 0, gg = 0, b = 0;
      for (let sy = 0; sy < ss; sy++) {
        let o = ((row0 + sy) * gw + col0) * 3;
        for (let sx = 0; sx < ss; sx++) {
          r += g[o];
          gg += g[o + 1];
          b += g[o + 2];
          o += 3;
        }
      }
      d[i] += r * inv;
      d[i + 1] += gg * inv;
      d[i + 2] += b * inv;
      i += 3;
    }
  }
}

/**
 * Post-filter radii are in pixels, so they must scale with the frame or a 4K
 * master gets a tighter, harsher look than the 1080p cut it was approved at.
 */
const PS = Math.max(0.5, H / 1080);

function renderFrame(t: number): Buffer {
  let f = film.render(t);
  f = applyTransition(f, t);
  // post: bloom on the hot values only, a touch of aberration, fine grain
  f = FX.bloom(f, { threshold: 0.78, radius: Math.max(3, 4 * PS), intensity: 0.26, wide: 0.16 });
  f = FX.chromaticAberration(f, 0.1 * PS);
  scrim(f);
  FX.vignette(f, 0.5, 2.2);
  FX.grain(f, t, 0.002);
  // graphics last: crisp, unbloomed, at full contrast
  compositeType(f, film.gfx, film.ss);
  f.toSRGB8(rgb);
  return encodePNG(rgb, W, H);
}

if (args.has('stills')) {
  const dir = join(OUT, 'stills');
  mkdirSync(dir, { recursive: true });
  for (const t of (args.get('stills') ?? '').split(',').filter(Boolean).map(Number)) {
    const s = performance.now();
    writeFileSync(join(dir, `still_${t.toFixed(2)}.png`), renderFrame(t));
    console.log(`[still] t=${t.toFixed(2)} ${(performance.now() - s).toFixed(0)}ms`);
  }
  process.exit(0);
}

mkdirSync(FRAME_DIR, { recursive: true });


/* ------------------------------------------------------------------ worker */
/* Each worker process renders one contiguous frame range and exits. Two cores,
 * so two workers — that is what keeps a four-pass schedule affordable here. */
const WORKER = args.get('worker');
if (WORKER) {
  const [a, b] = WORKER.split(':').map(Number);
  for (let i = a; i < b; i++) {
    writeFileSync(join(FRAME_DIR, `f_${String(i).padStart(5, '0')}.png`), renderFrame(i / FPS));
    if ((i - a) % 60 === 0) process.stdout.write(`\r[worker ${a}-${b}] ${i - a}/${b - a}`);
  }
  process.stdout.write(`\n[worker ${a}-${b}] done\n`);
  process.exit(0);
}

const first = Math.round(START * FPS);
const last = Math.round(END * FPS);
const total = last - first;

if (!args.has('resume') && existsSync(FRAME_DIR)) rmSync(FRAME_DIR, { recursive: true, force: true });
mkdirSync(FRAME_DIR, { recursive: true });

/* ------------------------------------------------------------------- render */
const ff = process.env.FFMPEG ?? join(ROOT, 'tools/ffmpeg');

function encode(): void {
  const r = spawnSync(
    ff,
    [
      '-y', '-v', 'error',
      '-framerate', String(FPS),
      '-start_number', String(first),
      '-i', join(FRAME_DIR, 'f_%05d.png'),
      ...(existsSync(AUDIO) ? ['-i', AUDIO] : []),
      '-c:v', 'libx264', '-preset', 'slow', '-crf', String(CRF), '-pix_fmt', 'yuv420p',
      // keep fine detail (type edges, contact stripes) rather than flattening it
      '-x264-params', 'aq-mode=3:deblock=-1,-1',
      '-profile:v', 'high', '-movflags', '+faststart',
      ...(existsSync(AUDIO) ? ['-c:a', 'aac', '-b:a', '192k', '-shortest'] : []),
      MP4,
    ],
    { stdio: 'inherit' },
  );
  if (r.status !== 0) {
    console.error('[encode] ffmpeg failed');
    process.exit(1);
  }
}

function gates(): void {
  console.log('\n--- gates ---');
  const results: unknown[] = [];
  const all = [
    slideshowGate(MP4, Math.min(FPS, 30)),
    scoreSequence(join(OUT, 'stills'), 1),
    freezeGate(MP4),
    transitionAudit(EDL.map((e) => ({ type: e.kind }))),
    existsSync(AUDIO) ? audioGate(AUDIO) : null,
  ];
  for (const g of all) {
    if (!g) continue;
    results.push(g);
    console.log(`${g.pass ? 'PASS' : 'FAIL'}  ${g.name}`, JSON.stringify(g.metrics));
    for (const n of g.notes) console.log(`      note: ${n}`);
  }
  const logPath = join(LOGS, 'gate_report.json');
  const prev = existsSync(logPath) ? JSON.parse(readFileSync(logPath, 'utf8')) : [];
  writeFileSync(logPath, JSON.stringify([...prev, { tag: TAG, pass: PASS, at: new Date().toISOString(), results }], null, 2));
}

function logIteration(ms: number): void {
  const logPath = join(LOGS, 'iteration_log.json');
  const log = existsSync(logPath) ? JSON.parse(readFileSync(logPath, 'utf8')) : { scenes: {} };
  const entry = {
    pass: PASS,
    tag: TAG,
    resolution: `${W}x${H}`,
    fps: FPS,
    frames: total,
    crf: CRF,
    at: new Date().toISOString(),
    minutes: Number((ms / 60000).toFixed(2)),
  };
  const names: Record<string, string> = {
    s1: 's1_title', s2: 's2_silicon', s3: 's3_yield', s4: 's4_hbm',
    s5: 's5_euv', s6: 's6_supply', s7: 's7_bom', s8: 's8_answer',
  };
  for (const scene of SHOTS) {
    const key = names[scene.id] ?? scene.id;
    const rec = log.scenes[key] ?? { iterations: 0, passes: [] };
    rec.passes = [...(rec.passes ?? []), { ...entry, sceneStart: scene.start, sceneEnd: scene.end }];
    rec.iterations = rec.passes.length + (rec.designIterations ?? 0);
    log.scenes[key] = rec;
  }
  log.updatedAt = new Date().toISOString();
  writeFileSync(logPath, JSON.stringify(log, null, 2));
}

function afterRender(ms: number): void {
  logIteration(ms);
  encode();
  if (args.has('gates')) gates();
  console.log(`[done] ${MP4}  (${total} frames @ ${FPS}fps in ${(ms / 60000).toFixed(1)} min)`);
}

const JOBS = Math.max(1, num('jobs', Number(process.env.JOBS ?? 2)));
if (JOBS > 1) {
  const chunk = Math.ceil(total / JOBS);
  const kids: import('node:child_process').ChildProcess[] = [];
  const started = performance.now();
  for (let k = 0; k < JOBS; k++) {
    const a = first + k * chunk;
    const b = Math.min(last, a + chunk);
    if (a >= b) continue;
    const rest = process.argv.slice(2).filter((x) => !x.startsWith('--worker'));
    kids.push(spawn(process.execPath, [...process.execArgv, fileURLToPath(import.meta.url), ...rest, `--worker=${a}:${b}`], { stdio: ['ignore', 'inherit', 'inherit'] }));
  }
  Promise.all(kids.map((k) => new Promise<void>((res) => k.on('exit', () => res())))).then(() => {
    const ms = performance.now() - started;
    console.log(`\n[parallel] ${total} frames on ${JOBS} workers in ${(ms / 60000).toFixed(1)} min`);
    afterRender(ms);
  });
} else {
  for (let i = first; i < last; i++) {
    writeFileSync(join(FRAME_DIR, `f_${String(i).padStart(5, '0')}.png`), renderFrame(i / FPS));
    const done = i - first + 1;
    if (done % 120 === 0 || done === total) {
      const el = (performance.now() - t0) / 1000;
      const per = el / done;
      process.stdout.write(`\r[pass ${PASS} ${TAG}] ${done}/${total}  ${(per * 1000).toFixed(0)}ms/f  eta ${((total - done) * per).toFixed(0)}s   `);
    }
  }
  process.stdout.write('\n');
  afterRender(performance.now() - t0);
}
