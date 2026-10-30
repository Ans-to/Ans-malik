/**
 * wire.ts — procedural 3D geometry: subdivided icospheres and shape morphing.
 *
 * One vertex buffer, many silhouettes. Morphing between them on the beat is
 * the cheapest way to get "liquid 3D" without a modelling package.
 */

import type { Vec3 } from '../core/math.ts';
import type { Mesh } from './stage.ts';

const ICO_V: Vec3[] = (() => {
  const t = (1 + Math.sqrt(5)) / 2;
  const raw: Vec3[] = [
    [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
    [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
    [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
  ];
  return raw.map((v) => {
    const l = Math.hypot(v[0], v[1], v[2]);
    return [v[0] / l, v[1] / l, v[2] / l] as Vec3;
  });
})();

const ICO_F: Array<[number, number, number]> = [
  [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
  [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
  [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
  [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
];

/** Unit icosphere with deduplicated edges. `subdiv` 0..2 keeps edge count sane. */
export function icosphere(subdiv = 1): Mesh {
  let verts = ICO_V.map((v) => [...v] as Vec3);
  let faces = ICO_F.map((f) => [...f] as [number, number, number]);

  for (let s = 0; s < subdiv; s++) {
    const cache = new Map<string, number>();
    const mid = (a: number, b: number): number => {
      const key = a < b ? `${a}_${b}` : `${b}_${a}`;
      const hit = cache.get(key);
      if (hit !== undefined) return hit;
      const va = verts[a];
      const vb = verts[b];
      const m: Vec3 = [(va[0] + vb[0]) / 2, (va[1] + vb[1]) / 2, (va[2] + vb[2]) / 2];
      const l = Math.hypot(m[0], m[1], m[2]) || 1;
      verts.push([m[0] / l, m[1] / l, m[2] / l]);
      cache.set(key, verts.length - 1);
      return verts.length - 1;
    };
    const next: Array<[number, number, number]> = [];
    for (const [a, b, c] of faces) {
      const ab = mid(a, b);
      const bc = mid(b, c);
      const ca = mid(c, a);
      next.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
    }
    faces = next;
  }

  const seen = new Set<string>();
  const edges: Array<[number, number]> = [];
  for (const [a, b, c] of faces) {
    for (const [p, q] of [[a, b], [b, c], [c, a]] as Array<[number, number]>) {
      const key = p < q ? `${p}_${q}` : `${q}_${p}`;
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push([Math.min(p, q), Math.max(p, q)]);
    }
  }
  return { verts, edges };
}

export type ShapeName = 'sphere' | 'torus' | 'cube' | 'octa' | 'knot' | 'ring';

/** Remap a unit-sphere direction onto another silhouette. */
export function shapePoint(d: Vec3, shape: ShapeName, scale = 1): Vec3 {
  const [x, y, z] = d;
  switch (shape) {
    case 'sphere':
      return [x * scale, y * scale, z * scale];
    case 'torus': {
      const u = Math.atan2(z, x);
      const v = Math.asin(Math.max(-1, Math.min(1, y)));
      const R = 0.72;
      const r = 0.34;
      const rr = R + r * Math.cos(v * 2);
      return [(rr * Math.cos(u)) * scale, r * Math.sin(v * 2) * scale, (rr * Math.sin(u)) * scale];
    }
    case 'cube': {
      const m = Math.max(Math.abs(x), Math.abs(y), Math.abs(z)) || 1;
      return [(x / m) * scale * 0.82, (y / m) * scale * 0.82, (z / m) * scale * 0.82];
    }
    case 'octa': {
      const m = Math.abs(x) + Math.abs(y) + Math.abs(z) || 1;
      return [(x / m) * scale * 1.25, (y / m) * scale * 1.25, (z / m) * scale * 1.25];
    }
    case 'knot': {
      const u = Math.atan2(z, x);
      const v = Math.asin(Math.max(-1, Math.min(1, y)));
      const r1 = 0.62;
      const r2 = 0.24;
      const a = u * 2 + v * 0.4;
      const rr = r1 + r2 * Math.cos(3 * u);
      return [rr * Math.cos(a) * scale, r2 * Math.sin(3 * u) * scale * 1.6, rr * Math.sin(a) * scale];
    }
    case 'ring': {
      const u = Math.atan2(z, x);
      const v = Math.asin(Math.max(-1, Math.min(1, y)));
      const r = 0.95 + Math.sin(u * 3) * 0.05;
      return [Math.cos(u) * r * scale, v * 0.14 * scale + Math.sin(v * 3) * 0.05, Math.sin(u) * r * scale];
    }
  }
}

/** Interpolate the same topology between two silhouettes. */
export function morph(base: Mesh, a: ShapeName, b: ShapeName, t: number, scale = 1): Mesh {
  const k = t < 0 ? 0 : t > 1 ? 1 : t;
  const verts = base.verts.map((d) => {
    const pa = shapePoint(d, a, scale);
    const pb = shapePoint(d, b, scale);
    return [
      pa[0] + (pb[0] - pa[0]) * k,
      pa[1] + (pb[1] - pa[1]) * k,
      pa[2] + (pb[2] - pa[2]) * k,
    ] as Vec3;
  });
  return { verts, edges: base.edges };
}

/** Deterministic particle field (sphere shell + drifting dust). */
export function particleField(count: number, radius: number, seed = 1): Vec3[] {
  const pts: Vec3[] = [];
  let s = seed * 9301 + 49297;
  const rnd = (): number => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
  for (let i = 0; i < count; i++) {
    const theta = rnd() * Math.PI * 2;
    const phi = Math.acos(2 * rnd() - 1);
    const r = radius * (0.35 + rnd() * 0.65);
    pts.push([
      Math.sin(phi) * Math.cos(theta) * r,
      Math.cos(phi) * r * 0.7,
      Math.sin(phi) * Math.sin(theta) * r,
    ]);
  }
  return pts;
}

/** A ring of points — used for the "portal" logo beat. */
export function ring(count: number, radius: number, tilt = 0): Vec3[] {
  const out: Vec3[] = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    out.push([Math.cos(a) * radius, Math.sin(a) * radius * Math.cos(tilt), Math.sin(a) * radius * Math.sin(tilt)]);
  }
  return out;
}
