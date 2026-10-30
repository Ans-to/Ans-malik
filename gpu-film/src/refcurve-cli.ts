/**
 * refcurve-cli.ts — derive motion curves from your own reference clips.
 *   npm run film:refcurve -- clip.mp4 dolly_in
 * Writes assets/curves/<name>.json, which supersedes the stored fallback.
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractMotionCurve } from './refcurve.ts';

const [path, name] = process.argv.slice(2);
if (!path || !name) {
  console.error('usage: refcurve-cli.ts <clip.mp4> <curve_name>');
  process.exit(1);
}
const dir = join(dirname(fileURLToPath(import.meta.url)), '../assets/curves');
mkdirSync(dir, { recursive: true });
const c = extractMotionCurve(path, name);
writeFileSync(join(dir, `${name}.json`), JSON.stringify(c, null, 2));
console.log(`wrote ${name}.json  (${c.samples.length} samples over ${c.duration.toFixed(2)}s)`);
console.log(c.method);
void spawnSync;
