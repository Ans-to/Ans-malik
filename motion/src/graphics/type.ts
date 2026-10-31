/**
 * type.ts — a filled display typeface, drawn in code.
 *
 * The previous approach (1px single-stroke letters) read as a CAD plot, not as
 * typography. This module generates a HEAVY monoline display face: every glyph
 * is a capsule-swept skeleton of stem width 0.17 em, rasterised into a
 * per-call coverage mask so overlapping strokes union instead of double-adding.
 *
 * That mask is the important part: it lets type behave like solid ink on a
 * light table — flat colour, hard edges, no bloom-seams — which is what makes
 * large type look designed instead of rendered.
 */

import { Frame, type RGB } from '../core/raster.ts';
import type { Camera } from './stage.ts';
import type { Vec3 } from '../core/math.ts';

export type Pt = [number, number];

const STEM = 0.17;

interface Glyph {
  w: number;
  /** polylines in a box [0..w] × [0..1] (cap height = 1) */
  strokes: Pt[][];
  /** extra side bearing in em, so narrow glyphs don't read as double-spaced */
  bear?: number;
}

const arc = (cx: number, cy: number, rx: number, ry: number, a0: number, a1: number, steps = 24): Pt[] => {
  const out: Pt[] = [];
  for (let i = 0; i <= steps; i++) {
    const a = ((a0 + (a1 - a0) * (i / steps)) * Math.PI) / 180;
    out.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]);
  }
  return out;
};

const GAP = STEM / 2;

/**
 * Glyphs. Coordinates are metric: the renderer insets by half a stem so the
 * ink lands exactly on the box edges.
 */
const G: Record<string, Glyph> = {};

G['A'] = { w: 0.74, strokes: [[[0, 0], [0.37, 1], [0.74, 0]], [[0.15, 0.34], [0.59, 0.34]]] };
G['B'] = {
  w: 0.66,
  strokes: [
    [[0, 0], [0, 1]],
    [[0, 1], [0.33, 1], [0.55, 0.88], [0.55, 0.63], [0.33, 0.52], [0, 0.52]],
    [[0.33, 0.52], [0.58, 0.4], [0.58, 0.13], [0.4, 0], [0, 0]],
  ],
};
G['C'] = { w: 0.68, strokes: [arc(0.34, 0.5, 0.32, 0.48, 48, 312, 26)] };
G['D'] = { w: 0.68, strokes: [[[0, 0], [0, 1], [0.24, 1], [0.62, 0.8], [0.62, 0.2], [0.24, 0], [0, 0]]] };
G['E'] = { w: 0.58, strokes: [[[0.58, 1], [0, 1], [0, 0], [0.58, 0]], [[0, 0.52], [0.46, 0.52]]] };
G['F'] = { w: 0.56, strokes: [[[0.56, 1], [0, 1], [0, 0]], [[0, 0.52], [0.44, 0.52]]] };
G['G'] = {
  w: 0.72,
  strokes: [
    arc(0.36, 0.5, 0.33, 0.48, 48, 330, 26),
    [[0.72, 0.46], [0.38, 0.46]],
  ],
};
G['H'] = { w: 0.66, strokes: [[[0, 0], [0, 1]], [[0.66, 0], [0.66, 1]], [[0, 0.54], [0.66, 0.54]]] };
G['I'] = { w: 0.17, strokes: [[[0.085, 0], [0.085, 1]]], bear: 0.09 };
G['J'] = { w: 0.56, strokes: [[[0.56, 1], [0.56, 0.3], ...arc(0.28, 0.3, 0.28, 0.3, 0, -180, 16).map(([x, y]) => [x, y] as Pt)]] };
G['K'] = { w: 0.64, strokes: [[[0, 0], [0, 1]], [[0.62, 1], [0, 0.36]], [[0.2, 0.56], [0.64, 0]]] };
G['L'] = { w: 0.56, strokes: [[[0, 1], [0, 0], [0.56, 0]]] };
G['M'] = { w: 0.9, strokes: [[[0, 0], [0, 1], [0.45, 0.16], [0.9, 1], [0.9, 0]]] };
G['N'] = { w: 0.68, strokes: [[[0, 0], [0, 1], [0.68, 0], [0.68, 1]]] };
G['O'] = { w: 0.8, strokes: [arc(0.4, 0.5, 0.4, 0.5, 0, 360, 44)] };
G['P'] = { w: 0.62, strokes: [[[0, 0], [0, 1], [0.34, 1], [0.62, 0.84], [0.62, 0.64], [0.34, 0.5], [0, 0.5]]] };
G['Q'] = { w: 0.8, strokes: [arc(0.4, 0.5, 0.4, 0.5, 0, 360, 44), [[0.5, 0.18], [0.82, -0.08]]] };
G['R'] = { w: 0.64, strokes: [[[0, 0], [0, 1], [0.34, 1], [0.64, 0.84], [0.64, 0.64], [0.34, 0.5], [0, 0.5]], [[0.28, 0.5], [0.64, 0]]] };
G['S'] = {
  w: 0.64,
  strokes: [[[0.62, 0.84], [0.44, 1], [0.16, 1], [0, 0.86], [0, 0.66], [0.16, 0.53], [0.44, 0.47], [0.62, 0.34], [0.62, 0.14], [0.46, 0], [0.16, 0], [0, 0.16]]],
};
G['T'] = { w: 0.68, strokes: [[[0, 1], [0.68, 1]], [[0.34, 1], [0.34, 0]]] };
G['U'] = { w: 0.68, strokes: [[[0, 1], [0, 0.3], ...arc(0.34, 0.3, 0.34, 0.3, 180, 360, 18).map(([x, y]) => [x, y] as Pt), [0.68, 1]]] };
G['V'] = { w: 0.74, strokes: [[[0, 1], [0.37, 0], [0.74, 1]]] };
G['W'] = { w: 1.02, strokes: [[[0, 1], [0.25, 0], [0.51, 0.66], [0.77, 0], [1.02, 1]]] };
G['X'] = { w: 0.7, strokes: [[[0, 0], [0.7, 1]], [[0, 1], [0.7, 0]]] };
G['Y'] = { w: 0.72, strokes: [[[0, 1], [0.36, 0.48], [0.72, 1]], [[0.36, 0.48], [0.36, 0]]] };
G['Z'] = { w: 0.66, strokes: [[[0, 1], [0.66, 1], [0, 0], [0.66, 0]]] };

G['0'] = { w: 0.72, strokes: [arc(0.36, 0.5, 0.36, 0.5, 0, 360, 40)] };
G['1'] = { w: 0.4, strokes: [[[0.06, 0.74], [0.28, 0.98], [0.28, 0]]] , bear: 0.13};
G['2'] = { w: 0.66, strokes: [[[0, 0.8], [0.16, 0.98], [0.5, 0.98], [0.66, 0.8], [0.66, 0.6], [0, 0], [0.66, 0]]] };
G['3'] = { w: 0.64, strokes: [[[0.02, 0.86], [0.18, 1], [0.46, 1], [0.62, 0.84], [0.62, 0.6], [0.42, 0.48], [0.18, 0.48]], [[0.42, 0.48], [0.62, 0.36], [0.62, 0.14], [0.44, 0], [0.16, 0], [0, 0.14]]] };
G['4'] = { w: 0.7, strokes: [[[0.5, 0], [0.5, 1], [0, 0.28], [0.7, 0.28]]] };
G['5'] = { w: 0.62, strokes: [[[0.58, 1], [0.08, 1], [0.04, 0.54], [0.22, 0.62], [0.44, 0.6], [0.58, 0.46], [0.6, 0.14], [0.44, 0], [0.16, 0], [0, 0.12]]] };
G['6'] = { w: 0.64, strokes: [[[0.56, 0.9], [0.38, 1], [0.18, 0.94], [0.04, 0.7], [0.02, 0.32], [0.16, 0.06], [0.34, 0], [0.52, 0.06], [0.62, 0.24], [0.6, 0.44], [0.44, 0.56], [0.22, 0.56], [0.04, 0.42]]] };
G['7'] = { w: 0.62, strokes: [[[0, 1], [0.62, 1], [0.22, 0]]] };
G['8'] = { w: 0.66, strokes: [arc(0.33, 0.76, 0.27, 0.24, 0, 360, 30), arc(0.33, 0.26, 0.33, 0.26, 0, 360, 34)] };
G['9'] = { w: 0.64, strokes: [[[0.6, 0.58], [0.42, 0.44], [0.2, 0.44], [0.04, 0.58], [0.04, 0.78], [0.2, 0.98], [0.4, 1], [0.56, 0.9], [0.62, 0.68], [0.6, 0.26], [0.48, 0.04], [0.3, 0], [0.14, 0.06]]] };

G[' '] = { w: 0.3, strokes: [] };
G['.'] = { w: 0.17, strokes: [[[0.085, 0.06], [0.085, 0.08]]] , bear: 0.1};
G[':'] = { w: 0.17, strokes: [[[0.085, 0.2], [0.085, 0.24]], [[0.085, 0.68], [0.085, 0.72]]] , bear: 0.1};
G['-'] = { w: 0.46, strokes: [[[0.04, 0.48], [0.42, 0.48]]] };
G['_'] = { w: 0.6, strokes: [[[0, -0.14], [0.6, -0.14]]] };
G['/'] = { w: 0.44, strokes: [[[0, 0], [0.44, 1]]] };
G['+'] = { w: 0.5, strokes: [[[0.25, 0.2], [0.25, 0.76]], [[0, 0.48], [0.5, 0.48]]] };
G[','] = { w: 0.17, strokes: [[[0.085, 0.12], [0.085, -0.08]]] , bear: 0.1};
G['·'] = { w: 0.17, strokes: [[[0.085, 0.44], [0.085, 0.46]]] , bear: 0.1};
G['!'] = { w: 0.17, strokes: [[[0.085, 0.32], [0.085, 1]], [[0.085, 0.02], [0.085, 0.04]]] , bear: 0.1};
G['$'] = { w: 0.66, strokes: [
  [[0.6, 0.86], [0.42, 1.0], [0.18, 1.0], [0.02, 0.86], [0.02, 0.68], [0.18, 0.56], [0.44, 0.5], [0.6, 0.38], [0.6, 0.18], [0.44, 0.02], [0.18, 0.02], [0.02, 0.14]],
  [[0.31, 0.1], [0.31, 0.92]],
] };
G['&'] = { w: 0.72, strokes: [[[0.7, 0.02], [0.14, 0.62], [0.14, 0.84], [0.28, 1], [0.44, 0.9], [0.44, 0.72], [0.06, 0.44], [0.06, 0.2], [0.24, 0], [0.46, 0], [0.7, 0.26]]] };
G['%'] = { w: 0.78, strokes: [arc(0.16, 0.82, 0.15, 0.17, 0, 360, 16), arc(0.62, 0.18, 0.15, 0.17, 0, 360, 16), [[0, 0], [0.78, 1]]] };

export const glyph = (ch: string): Glyph => G[ch.toUpperCase()] ?? G['?'] ?? G[' '];

/* ------------------------------------------------------------ coverage mask */

class Mask {
  w = 0;
  h = 0;
  data = new Float32Array(0);
  x0 = 0;
  y0 = 0;

  ensure(x0: number, y0: number, w: number, h: number): void {
    if (w > this.w || h > this.h) {
      this.w = Math.max(w, this.w);
      this.h = Math.max(h, this.h);
      this.data = new Float32Array(this.w * this.h);
    }
    this.x0 = x0;
    this.y0 = y0;
  }

  /** Zero only the sub-rectangle we are about to draw (stride-aware). */
  clear(w: number, h: number): void {
    const rows = Math.min(h, this.h);
    for (let y = 0; y < rows; y++) this.data.fill(0, y * this.w, y * this.w + Math.min(w, this.w));
  }

  /**
   * Capsule sweep with analytic AA, unioned by max.
   * `flatA` / `flatB` cut the stroke square at that endpoint: a round capsule
   * minus the half-plane beyond the end is exactly the butt-capped rectangle,
   * which is what makes terminals read as cut rather than blown up.
   * (ox, oy) = origin of this mask in screen space.
   */
  capsule(
    ax: number, ay: number, bx: number, by: number, r: number, ox: number, oy: number,
    flatA = false, flatB = false,
  ): void {
    const pad = r + 1;
    const minX = Math.max(0, Math.floor(Math.min(ax, bx) - pad - ox));
    const maxX = Math.min(this.w - 1, Math.ceil(Math.max(ax, bx) + pad - ox));
    const minY = Math.max(0, Math.floor(Math.min(ay, by) - pad - oy));
    const maxY = Math.min(this.h - 1, Math.ceil(Math.max(ay, by) + pad - oy));
    if (maxX < minX || maxY < minY) return;

    const w = this.w;
    const d = this.data;
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy || 1e-9;
    const segLen = Math.sqrt(len2);
    const ux = dx / segLen;
    const uy = dy / segLen;
    const rIn = Math.max(0, r - 0.5);
    const rOut = r + 0.5;
    const rIn2 = rIn * rIn;
    const rOut2 = rOut * rOut;

    for (let y = minY; y <= maxY; y++) {
      const py = y + 0.5 + oy;
      const row = y * w;
      for (let x = minX; x <= maxX; x++) {
        const px = x + 0.5 + ox;
        let t = ((px - ax) * dx + (py - ay) * dy) / len2;
        t = t < 0 ? 0 : t > 1 ? 1 : t;
        const ex = ax + dx * t - px;
        const ey = ay + dy * t - py;
        const d2 = ex * ex + ey * ey;
        if (d2 > rOut2) continue;
        let cov = d2 <= rIn2 ? 1 : 1 - (Math.sqrt(d2) - rIn);
        if (flatA || flatB) {
          const along = (px - ax) * ux + (py - ay) * uy;
          if (flatA && along < 0.5) cov *= Math.max(0, along + 0.5);
          else if (flatB && along > segLen - 0.5) cov *= Math.max(0, segLen - along + 0.5);
        }
        if (cov <= 0) continue;
        const i = row + x;
        if (cov > d[i]) d[i] = cov;
      }
    }
  }
}

const mask = new Mask();

/* --------------------------------------------------------------- text draw */

export interface CharState {
  opacity?: number;
  scale?: number;
  scaleX?: number;
  scaleY?: number;
  offset?: [number, number, number];
  rotZ?: number;
  /** vertical reveal, keeps the BOTTOM portion: 0 = hidden, 1 = full */
  reveal?: number;
  /** horizontal reveal, keeps the LEFT portion: 0 = hidden, 1 = full */
  wipe?: number;
  glow?: number;
}

export interface TextSpec {
  text: string;
  /** cap height in world units */
  size: number;
  position: Vec3;
  rotation?: Vec3;
  /** horizontal squeeze (1 = normal, 0.85 = condensed) */
  condense?: number;
  align?: 'left' | 'center' | 'right';
  /** em, negative = tighter */
  tracking?: number;
  color: RGB;
  weight?: number;
  opacity?: number;
  /** draw order offset so overlapping glyphs read in depth */
  perChar?: (i: number, n: number) => CharState;
  /** distance fog */
  fog?: number;
  /** 0..1 extra exposure for hot highlights */
  emissive?: number;
}

function applyEuler(p: Vec3, r: Vec3): Vec3 {
  const [rx, ry, rz] = r;
  const cx = Math.cos(rx), sx = Math.sin(rx);
  const cy = Math.cos(ry), sy = Math.sin(ry);
  const cz = Math.cos(rz), sz = Math.sin(rz);
  let x = p[0], y = p[1] * cx - p[2] * sx, z = p[1] * sx + p[2] * cx;
  const x2 = x * cy + z * sy;
  const z2 = -x * sy + z * cy;
  x = x2; z = z2;
  return [x * cz - y * sz, x * sz + y * cz, z];
}

/** Width of a string in em units (before `size` scaling). */
export function measure(text: string, tracking = 0, condense = 1): number {
  let x = 0;
  for (const ch of text) {
    const g = glyph(ch);
    x += g.w * condense + (g.bear ?? 0) + tracking;
  }
  return Math.max(0, x - tracking);
}

interface Seg {
  ax: number;
  ay: number;
  bx: number;
  by: number;
  r: number;
  a: number;
  flatA?: boolean;
  flatB?: boolean;
}

/**
 * Draw filled display type through the 3D camera.
 *
 * Each glyph is rasterised into its own coverage mask and composited with its
 * own alpha, so per-character opacity, reveal wipes and stagger all work while
 * overlapping strokes still union cleanly (no bright seams inside a letter).
 */
export function drawType(
  frame: Frame,
  cam: Camera,
  spec: TextSpec,
): { x0: number; y0: number; x1: number; y1: number } | null {
  const tracking = spec.tracking ?? 0;
  const condense = spec.condense ?? 1;
  const rot = spec.rotation ?? [0, 0, 0];
  const weight = (spec.weight ?? 1) * STEM;
  const opacity = spec.opacity ?? 1;
  if (opacity <= 0.002) return null;

  const totalW = measure(spec.text, tracking, condense);
  let pen = spec.align === 'center' ? -totalW / 2 : spec.align === 'right' ? -totalW : 0;

  const chars = [...spec.text];
  const n = chars.length;
  const inset = STEM / 2;
  const col = spec.color;
  const emis = spec.emissive ?? 1;
  const fog = spec.fog ?? 1;

  let allX0 = Infinity, allY0 = Infinity, allX1 = -Infinity, allY1 = -Infinity;

  for (let ci = 0; ci < n; ci++) {
    const ch = chars[ci];
    const g = glyph(ch);
    const adv = g.w * condense + (g.bear ?? 0);
    const st = spec.perChar ? spec.perChar(ci, n) : {};
    const op = (st.opacity ?? 1) * opacity;

    if (op > 0.002 && ch !== ' ' && g.strokes.length) {
      const sc = st.scale ?? 1;
      const scx = sc * (st.scaleX ?? 1);
      const scy = sc * (st.scaleY ?? 1);
      const off = st.offset ?? [0, 0, 0];
      const rz = st.rotZ ?? 0;
      const cxEm = pen + adv / 2;
      const cs = Math.cos(rz), sn = Math.sin(rz);
      const gw = Math.max(1e-4, g.w);

      // author space -> world space, insetting by half a stem so the ink lands
      // exactly on the glyph box
      const toWorld = (gx: number, gy: number): Vec3 => {
        const mx = inset + (gx / gw) * (gw - 2 * inset);
        const my = inset + gy * (1 - 2 * inset); // 0 at the baseline, 1 at cap height
        let lx = mx - gw / 2;
        const ly = my;
        const rx2 = (lx * cs - ly * sn) * scx * spec.size;
        const ry2 = (lx * sn + ly * cs) * scy * spec.size;
        return applyEuler(
          [(cxEm + off[0]) * spec.size + rx2, off[1] * spec.size + ry2, off[2] * spec.size],
          rot,
        );
      };

      const segs: Seg[] = [];
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

      for (const stroke of g.strokes) {
        // a stroke whose ends meet is a closed contour: keep round joins there
        const first = stroke[0];
        const last = stroke[stroke.length - 1];
        const closed = stroke.length > 2 && Math.hypot(first[0] - last[0], first[1] - last[1]) < 0.03;
        for (let i = 1; i < stroke.length; i++) {
          const p0 = toWorld(stroke[i - 1][0], stroke[i - 1][1]);
          const p1 = toWorld(stroke[i][0], stroke[i][1]);
          const w0: Vec3 = [p0[0] + spec.position[0], p0[1] + spec.position[1], p0[2] + spec.position[2]];
          const w1: Vec3 = [p1[0] + spec.position[0], p1[1] + spec.position[1], p1[2] + spec.position[2]];
          const s0 = cam.project(w0);
          const s1 = cam.project(w1);
          if (!s0.ok || !s1.ok) continue;
          const depth = (s0.depth + s1.depth) * 0.5;
          const pxPerUnit = cam.scaleAt(depth);
          const r = Math.max(0.35, (weight * spec.size * pxPerUnit) / 2) * ((scx + scy) / 2);
          const atten = Math.max(0, Math.min(1.2, 1.18 - (depth - 5) * 0.017 * fog));
          const alpha = op * atten;
          if (alpha <= 0.004) continue;
          // Butt caps only on axis-aligned terminals: a flat cut on a diagonal
          // or a curve reads as a spike, not as typography.
          const adx = Math.abs(s1.x - s0.x);
          const ady = Math.abs(s1.y - s0.y);
          const axisAligned = adx < 0.02 * Math.max(1, ady) || ady < 0.02 * Math.max(1, adx);
          segs.push({
            ax: s0.x, ay: s0.y, bx: s1.x, by: s1.y, r, a: alpha,
            flatA: !closed && axisAligned && i === 1,
            flatB: !closed && axisAligned && i === stroke.length - 1,
          });
          minX = Math.min(minX, s0.x, s1.x);
          maxX = Math.max(maxX, s0.x, s1.x);
          minY = Math.min(minY, s0.y, s1.y);
          maxY = Math.max(maxY, s0.y, s1.y);
        }
      }

      if (segs.length && isFinite(minX)) {
        // pad must cover the largest stroke radius, or thick glyphs get clipped
        let maxR = 0;
        for (const sgm of segs) if (sgm.r > maxR) maxR = sgm.r;
        const pad = Math.ceil(maxR) + 2;
        const bx0 = Math.max(0, Math.floor(minX - pad));
        const by0 = Math.max(0, Math.floor(minY - pad));
        const bw = Math.min(frame.w - bx0, Math.ceil(maxX + pad) - bx0);
        const bh = Math.min(frame.h - by0, Math.ceil(maxY + pad) - by0);

        if (bw > 0 && bh > 0) {
          mask.ensure(bx0, by0, bw, bh);
          mask.clear(bw, bh);
          for (const sg of segs) mask.capsule(sg.ax, sg.ay, sg.bx, sg.by, sg.r, bx0, by0, sg.flatA, sg.flatB);

          // reveal / wipe masks in screen space
          const rv = st.reveal === undefined ? 1 : Math.max(0, Math.min(1, st.reveal));
          const wv = st.wipe === undefined ? 1 : Math.max(0, Math.min(1, st.wipe));
          const cutY = maxY - (maxY - minY) * rv; // keep pixels below
          const cutX = minX + (maxX - minX) * wv; // keep pixels left of
          const alpha = segs[0].a;
          const md = mask.data;
          const fd = frame.data;
          const mw = mask.w;
          const yStart = Math.max(0, Math.floor(cutY - by0));
          const xEnd = Math.min(bw, Math.ceil(cutX - bx0));
          for (let y = yStart; y < bh; y++) {
            const fy = by0 + y;
            const rowM = y * mw;
            const rowF = fy * frame.w;
            for (let x = 0; x < xEnd; x++) {
              const cov = md[rowM + x];
              if (cov <= 0.002) continue;
              const k = cov * alpha * emis;
              const o = (rowF + bx0 + x) * 3;
              fd[o] += col[0] * k;
              fd[o + 1] += col[1] * k;
              fd[o + 2] += col[2] * k;
            }
          }
        }
      }
      allX0 = Math.min(allX0, minX);
      allY0 = Math.min(allY0, minY);
      allX1 = Math.max(allX1, maxX);
      allY1 = Math.max(allY1, maxY);
    }
    pen += adv + tracking;
  }

  if (!isFinite(allX0)) return null;
  return { x0: allX0, y0: allY0, x1: allX1, y1: allY1 };
}
