/**
 * engine3d.ts — a real 3D surface renderer: z-buffered triangle raster with
 * geometric shading, plus depth of field and volumetric beams.
 *
 * The earlier film only drew wireframes, which is why it read as a CAD plot.
 * Here every object is solid geometry lit by a key/fill/rim rig with a
 * procedural studio environment, rendered into linear HDR with a depth buffer,
 * then defocused by a physically-shaped circle-of-confusion. That combination —
 * solid form, specular highlight, shallow focus — is most of what makes product
 * motion graphics feel expensive.
 */

import { Frame, type RGB } from '../../motion/src/core/raster.ts';
import { clamp, mat4, multiply, norm, sub, type Mat4, type Vec3 } from '../../motion/src/core/math.ts';
import type { Camera } from '../../motion/src/graphics/stage.ts';

export interface Material {
  /** base colour, linear */
  albedo: RGB;
  /** 0 = mirror, 1 = chalk */
  rough: number;
  /** 0 = dielectric, 1 = metal */
  metal: number;
  /** self-illumination added regardless of light */
  emit?: RGB;
  /** fresnel rim strength */
  rim?: number;
}

export interface Face {
  a: number;
  b: number;
  c: number;
  m: Material;
}

export interface Mesh {
  v: Vec3[];
  f: Face[];
}

/** Studio environment: sky gradient + two soft boxes, sampled by direction. */
export interface Env {
  zenith: RGB;
  horizon: RGB;
  ground: RGB;
  key: Vec3;
  keyColor: RGB;
  keyPower: number;
  fill: Vec3;
  fillColor: RGB;
  fillPower: number;
  rim: Vec3;
  rimColor: RGB;
  rimPower: number;
  /** overall exposure */
  exposure: number;
}

export const studioEnv = (o: Partial<Env> = {}): Env => ({
  zenith: [0.06, 0.075, 0.10],
  horizon: [0.02, 0.022, 0.028],
  ground: [0.008, 0.008, 0.009],
  key: norm([-0.45, 0.75, 0.55]),
  keyColor: [1.0, 0.96, 0.9],
  keyPower: 2.2,
  fill: norm([0.8, 0.15, 0.45]),
  fillColor: [0.3, 0.4, 0.58],
  fillPower: 0.4,
  rim: norm([0.2, 0.35, -1.0]),
  rimColor: [0.5, 0.68, 1.0],
  rimPower: 1.1,
  exposure: 0.85,
  ...o,
});

/**
 * Depth buffer + triangle raster. One instance per frame; buffers are reused.
 */
export class Render3D {
  readonly w: number;
  readonly h: number;
  readonly depth: Float32Array;
  readonly frame: Frame;

  /** accumulated coverage per pixel, so AA blends are never double-counted. */
  private alpha = new Float32Array(0);

  constructor(w: number, h: number, frame?: Frame) {
    this.w = w;
    this.h = h;
    this.frame = frame ?? new Frame(w, h);
    // depth is stored as 1/distance (see draw()): interpolation of 1/z is
    // affine in screen space, which is the only way a z-buffer is correct on
    // large triangles. 0 means "nothing drawn yet".
    this.depth = new Float32Array(w * h);
    this.alpha = new Float32Array(w * h);
  }

  /** Reset the z-buffer (the colour buffer is owned by the caller). */
  reset(): void {
    this.depth.fill(0);
    this.alpha.fill(0);
  }

  private viewProject(cam: Camera, v: Vec3): [number, number, number] | null {
    // replicate Camera.project but keep view depth and reject behind-camera
    const p = cam.project(v);
    if (!p.ok) return null;
    // reconstruct eye-space distance from the camera eye
    const d = Math.hypot(v[0] - cam.eye[0], v[1] - cam.eye[1], v[2] - cam.eye[2]);
    return [p.x, p.y, d];
  }

  /**
   * Draw a mesh.
   * `world` is optional per-vertex transform applied first.
   */
  draw(cam: Camera, mesh: Mesh, env: Env, world?: (v: Vec3) => Vec3): void {
    const V = mesh.v;
    const n = V.length;
    const sx = new Float32Array(n);
    const sy = new Float32Array(n);
    const sz = new Float32Array(n);
    const wx = new Float32Array(n * 3);
    const okFlag = new Uint8Array(n);

    for (let i = 0; i < n; i++) {
      const w = world ? world(V[i]) : V[i];
      wx[i * 3] = w[0];
      wx[i * 3 + 1] = w[1];
      wx[i * 3 + 2] = w[2];
      const s = this.viewProject(cam, w);
      if (!s) {
        okFlag[i] = 0;
        continue;
      }
      okFlag[i] = 1;
      sx[i] = s[0];
      sy[i] = s[1];
      sz[i] = 1 / Math.max(1e-4, s[2]);
    }

    for (const face of mesh.f) {
      if (!okFlag[face.a] || !okFlag[face.b] || !okFlag[face.c]) continue;
      this.triangle(face, sx, sy, sz, wx, cam, env);
    }
  }

  private triangle(
    face: Face,
    sx: Float32Array,
    sy: Float32Array,
    sz: Float32Array,
    wx: Float32Array,
    cam: Camera,
    env: Env,
  ): void {
    const ia = face.a;
    const ib = face.b;
    const ic = face.c;
    let x0 = sx[ia], y0 = sy[ia], z0 = sz[ia];
    let x1 = sx[ib], y1 = sy[ib], z1 = sz[ib];
    let x2 = sx[ic], y2 = sy[ic], z2 = sz[ic];

    // world-space normal for shading (constant across the face: flat shading,
    // which is the correct look for machined/printed surfaces)
    const ax = wx[ia * 3], ay = wx[ia * 3 + 1], az = wx[ia * 3 + 2];
    const bx = wx[ib * 3], by = wx[ib * 3 + 1], bz = wx[ib * 3 + 2];
    const cx = wx[ic * 3], cy = wx[ic * 3 + 1], cz = wx[ic * 3 + 2];
    let nx = (by - ay) * (cz - az) - (bz - az) * (cy - ay);
    let ny = (bz - az) * (cx - ax) - (bx - ax) * (cz - az);
    let nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
    const nl = Math.hypot(nx, ny, nz) || 1;
    nx /= nl; ny /= nl; nz /= nl;
    // Coplanar triangles must shade identically. Float error in the world-space
    // cross product leaves them a hair apart, which shows up as a thin diagonal
    // seam across the middle of a large flat surface. Quantise to kill it.
    // coarser than float noise by two orders of magnitude, so two triangles
    // that are geometrically coplanar land on the identical normal
    nx = Math.round(nx * 512) / 512;
    ny = Math.round(ny * 512) / 512;
    nz = Math.round(nz * 512) / 512;

    // backface cull in screen space
    const area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (area >= -1e-9) return;

    const minX = Math.max(0, Math.floor(Math.min(x0, x1, x2)));
    const maxX = Math.min(this.w - 1, Math.ceil(Math.max(x0, x1, x2)));
    const minY = Math.max(0, Math.floor(Math.min(y0, y1, y2)));
    const maxY = Math.min(this.h - 1, Math.ceil(Math.max(y0, y1, y2)));
    if (maxX < minX || maxY < minY) return;

    const invArea = 1 / area;
    const m = face.m;
    const albedo = m.albedo;
    // view vector: towards the camera (approx per-face, good enough at these scales)
    let vx = cam.eye[0] - (ax + bx + cx) / 3;
    let vy = cam.eye[1] - (ay + by + cy) / 3;
    let vz = cam.eye[2] - (az + bz + cz) / 3;
    const vl = Math.hypot(vx, vy, vz) || 1;
    vx /= vl; vy /= vl; vz /= vl;

    const ndl = Math.max(0, nx * env.key[0] + ny * env.key[1] + nz * env.key[2]);
    const ndf = Math.max(0, nx * env.fill[0] + ny * env.fill[1] + nz * env.fill[2]);
    const ndr = Math.max(0, nx * env.rim[0] + ny * env.rim[1] + nz * env.rim[2]);
    // Blinn specular
    const halfX = env.key[0] + vx, halfY = env.key[1] + vy, halfZ = env.key[2] + vz;
    const hl = Math.hypot(halfX, halfY, halfZ) || 1;
    const ndh = Math.max(0, (nx * halfX + ny * halfY + nz * halfZ) / hl);
    const shininess = Math.pow(2, (1 - m.rough) * 9) + 2;
    const spec = Math.pow(ndh, shininess) * (1 - m.rough) * (0.12 + m.metal * 0.85);
    // environment reflection: sky above, ground below, cheap but directional
    const sky = clamp(ny * 0.5 + 0.5);
    const envR = sky * sky;
    const fres = Math.pow(1 - Math.max(0, nx * vx + ny * vy + nz * vz), 4);
    const rimAmt = (m.rim ?? 1) * (0.15 + fres * 1.1);

    // Lambert diffuse with an inverse-square-ish falloff baked into the power,
    // then energy split between diffuse and specular (metal has no diffuse).
    const kd = env.keyPower * ndl * 0.55;
    const fd = env.fillPower * ndf * 0.5;
    const rd = env.rimPower * ndr * 0.42;
    const diffuseMetal = 1 - m.metal * 0.92;

    const e = env.exposure;
    let r = albedo[0] * (env.keyColor[0] * kd * diffuseMetal + env.fillColor[0] * fd + env.rimColor[0] * rd * 0.5);
    let g = albedo[1] * (env.keyColor[1] * kd * diffuseMetal + env.fillColor[1] * fd + env.rimColor[1] * rd * 0.5);
    let b = albedo[2] * (env.keyColor[2] * kd * diffuseMetal + env.fillColor[2] * fd + env.rimColor[2] * rd * 0.5);

    // metal tints its reflection with its albedo; dielectrics get a white lobe
    const tintR = m.metal > 0.5 ? albedo[0] : 1;
    const tintG = m.metal > 0.5 ? albedo[1] : 1;
    const tintB = m.metal > 0.5 ? albedo[2] : 1;
    r += spec * env.keyColor[0] * tintR;
    g += spec * env.keyColor[1] * tintG;
    b += spec * env.keyColor[2] * tintB;

    // environment gradient reflected, weighted by fresnel
    const envW = (m.metal * 0.5 + 0.06);
    r += envR * (env.zenith[0] * 0.8 + env.horizon[0] * 0.4) * envW * tintR;
    g += envR * (env.zenith[1] * 0.8 + env.horizon[1] * 0.4) * envW * tintG;
    b += envR * (env.zenith[2] * 0.8 + env.horizon[2] * 0.4) * envW * tintB;

    r += env.rimColor[0] * rimAmt * 0.22;
    g += env.rimColor[1] * rimAmt * 0.22;
    b += env.rimColor[2] * rimAmt * 0.22;

    if (m.emit) {
      r += m.emit[0];
      g += m.emit[1];
      b += m.emit[2];
    }
    r *= e; g *= e; b *= e;

    const d = this.depth;
    const fd2 = this.frame.data;
    const W = this.w;

    // Edge lengths, so barycentrics can be turned into pixel distances: that is
    // what separates "solidly inside" from "crossing the boundary". Pixels that
    // straddle an edge get 4 sub-samples and a coverage blend — analytic-style
    // anti-aliasing that costs almost nothing, because only edge pixels do the
    // extra work. Without it every silhouette is a staircase, and a staircase
    // reads as low resolution no matter how good the shading is.
    const a2 = -area;
    const len0 = Math.hypot(x2 - x1, y2 - y1) || 1;
    const len1 = Math.hypot(x0 - x2, y0 - y2) || 1;
    const len2 = Math.hypot(x1 - x0, y1 - y0) || 1;
    const inv0 = a2 / len0;
    const inv1 = a2 / len1;
    const inv2 = a2 / len2;
    // 2x2 grid, NOT four points on the diagonal. A diagonal arrangement
    // under-samples any edge running at 45 degrees, which is exactly where
    // triangulation seams live.
    const OFFS: Array<[number, number]> = [
      [0.25, 0.25],
      [0.75, 0.25],
      [0.25, 0.75],
      [0.75, 0.75],
    ];
    const inside = (px: number, py: number, w0: number, w1: number, w2: number): boolean =>
      w0 >= 0 && w1 >= 0 && w2 >= 0;

    for (let y = minY; y <= maxY; y++) {
      const py = y + 0.5;
      for (let x = minX; x <= maxX; x++) {
        const px = x + 0.5;
        const w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) * invArea;
        const w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) * invArea;
        const w2 = 1 - w0 - w1;

        // distance (in pixels) from this sample to each of the three edges
        const dx0 = w0 * inv0;
        const dx1 = w1 * inv1;
        const dx2 = w2 * inv2;
        const minD = Math.min(dx0, dx1, dx2);
        if (minD < -1.0) continue; // wholly outside by more than a pixel

        // A pixel already covered at the same depth is an INTERIOR pixel — the
        // boundary between two triangles of the same surface. Let the winner
        // claim it outright: partial coverage there would let the two faces
        // average with each other and leave a dark stitch along every shared
        // edge. Anti-aliasing is only meaningful against the background.
        const zc = w0 * z0 + w1 * z1 + w2 * z2; // 1/distance
        const pix = y * W + x;
        const covered = d[pix] > 0;
        let cov = 1;
        if (minD < 1.0 && !covered) {
          // boundary pixel: 4 sub-samples, offset to the pixel corner
          let n = 0;
          for (let k = 0; k < 4; k++) {
            const sx2 = x + OFFS[k][0];
            const sy2 = y + OFFS[k][1];
            const q0 = ((x1 - sx2) * (y2 - sy2) - (x2 - sx2) * (y1 - sy2)) * invArea;
            const q1 = ((x2 - sx2) * (y0 - sy2) - (x0 - sx2) * (y2 - sy2)) * invArea;
            if (inside(sx2, sy2, q0, q1, 1 - q0 - q1)) n++;
          }
          cov = n / 4;
          if (cov === 0) continue;
        }

        const z = zc; // 1/distance: larger is nearer
        const i = pix;
        const bias = Math.max(2e-6, d[i] * 2e-4);
        const o = i * 3;

        if (z > d[i] + bias) {
          // NEARER surface: it wins the pixel. Where it only partly covers it
          // (silhouette edge) it blends over whatever was behind.
          d[i] = z;
          this.alpha[i] = cov;
          if (cov >= 1) {
            fd2[o] = r;
            fd2[o + 1] = g;
            fd2[o + 2] = b;
          } else {
            const keep = 1 - cov;
            fd2[o] = fd2[o] * keep + r * cov;
            fd2[o + 1] = fd2[o + 1] * keep + g * cov;
            fd2[o + 2] = fd2[o + 2] * keep + b * cov;
          }
        } else if (Math.abs(z - d[i]) <= bias) {
          // SAME surface: a neighbouring triangle of the same flat face (this is
          // the triangulation diagonal). Accumulate coverage so the two
          // contributions fill the pixel between them instead of doubling up or
          // leaving a stitch line.
          const a = this.alpha[i];
          if (a >= 0.999) continue;
          const add = cov * (1 - a);
          const keep = 1 - add;
          fd2[o] = fd2[o] * keep + r * add;
          fd2[o + 1] = fd2[o + 1] * keep + g * add;
          fd2[o + 2] = fd2[o + 2] * keep + b * add;
          this.alpha[i] = a + add;
        }
        // else: behind an existing surface — reject
      }
    }
  }

  /**
   * Depth of field from the z-buffer.
   * CoC is computed per pixel, then three progressively blurred copies of the
   * frame are blended by CoC. Near-field and far-field are treated separately
   * so a sharp foreground never bleeds into a soft background.
   */
  applyDOF(focus: number, aperture: number, maxRadius = 12): void {
    const { w, h, depth, frame } = this;
    if (aperture <= 0.001) return;

    // Level 0 is the UNBLURRED frame. This is the whole point: a depth-of-field
    // pass must be a no-op on the focus plane. (An earlier version started at
    // a radius-2 blur, so every frame was quietly softened everywhere — the
    // "it's blurry" that no amount of detail work could fix.)
    const mid = Math.max(2, Math.round(Math.min(maxRadius, 4)));
    const far = Math.max(mid + 1, Math.round(maxRadius));
    const orig = frame.data;
    const midBuf = blurFrame(frame, mid).data;
    const farBuf = blurFrame(frame, far).data;

    // Circle of confusion with a thin-lens response: quadratic in distance error,
    // not linear. A linear falloff starts softening the hero object itself, which
    // is what makes a render read as "blurry" rather than "cinematic"; the
    // squared curve keeps everything within ~40% of the focus plane genuinely
    // sharp and still dissolves the background completely.
    const coc = new Float32Array(w * h);
    const range = Math.max(0.05, focus * 0.55);
    for (let i = 0; i < w * h; i++) {
      // No geometry here: keep the ink black. Blurring empty background pulls a
      // smeared copy of the subject into it, which reads as haze around every
      // silhouette — the cheapest way to make a sharp render look soft. Depth on
      // the actual geometry is what defocus is for.
      const z = depth[i] > 0 ? 1 / depth[i] : Infinity;
      if (!isFinite(z)) {
        coc[i] = 0;
        continue;
      }
      const e2 = (z - focus) / range;
      coc[i] = clamp(e2 * e2 * aperture * 2.2);
    }

    // soften the CoC field so blur boundaries are not visible as contours
    const cocSoft = new Float32Array(w * h);
    const R = 2;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        let s2 = 0;
        let c2 = 0;
        for (let dy = -R; dy <= R; dy++) {
          const yy = clamp(y + dy, 0, h - 1) | 0;
          for (let dx = -R; dx <= R; dx++) {
            const xx = clamp(x + dx, 0, w - 1) | 0;
            s2 += coc[yy * w + xx];
            c2++;
          }
        }
        cocSoft[y * w + x] = s2 / c2;
      }
    }

    // Graded mix toward the blurred copies, never a hard switch. Handing whole
    // regions over to a heavy blur erases low-contrast surface detail across
    // wide areas (it wiped the wafer's die grid); a graded mix keeps local
    // contrast present everywhere and only softens it.
    for (let i = 0; i < w * h; i++) {
      const c = cocSoft[i];
      if (c <= 0.02) continue;
      const o = i * 3;
      const m = Math.min(1, c);
      const f2 = m * m * (3 - 2 * m); // smoothstep
      const g1 = f2 * 0.55;
      const g2 = (Math.max(0, f2 - 0.55) / 0.45) * 0.7;
      for (let k = 0; k < 3; k++) {
        const oi = o + k;
        const v1 = orig[oi] + (midBuf[oi] - orig[oi]) * g1;
        orig[oi] = v1 + (farBuf[oi] - v1) * g2;
      }
    }
  }
}

/** Separable box blur on a linear HDR frame (3 passes ≈ gaussian). */
export function blurFrame(src: Frame, radius: number): Frame {
  const { w, h } = src;
  const tmp = new Frame(w, h);
  const out = new Frame(w, h);
  out.data.set(src.data);
  const r = Math.max(1, Math.round(radius));
  for (let pass = 0; pass < 2; pass++) {
    for (let y = 0; y < h; y++) {
      for (let c = 0; c < 3; c++) {
        let sum = 0;
        const inv = 1 / (2 * r + 1);
        for (let k = -r; k <= r; k++) sum += out.data[(y * w + clamp(k, 0, w - 1)) * 3 + c];
        for (let x = 0; x < w; x++) {
          tmp.data[(y * w + x) * 3 + c] = sum * inv;
          const add = (y * w + clamp(x + r + 1, 0, w - 1)) * 3 + c;
          const sub2 = (y * w + clamp(x - r, 0, w - 1)) * 3 + c;
          sum += out.data[add] - out.data[sub2];
        }
      }
    }
    for (let x = 0; x < w; x++) {
      for (let c = 0; c < 3; c++) {
        let sum = 0;
        const inv = 1 / (2 * r + 1);
        for (let k = -r; k <= r; k++) sum += tmp.data[(clamp(k, 0, h - 1) * w + x) * 3 + c];
        for (let y = 0; y < h; y++) {
          out.data[(y * w + x) * 3 + c] = sum * inv;
          const add = (clamp(y + r + 1, 0, h - 1) * w + x) * 3 + c;
          const sub2 = (clamp(y - r, 0, h - 1) * w + x) * 3 + c;
          sum += tmp.data[add] - tmp.data[sub2];
        }
      }
    }
  }
  return out;
}

/* --------------------------------------------------------------- geometry */

export const box = (
  cx: number, cy: number, cz: number,
  sx: number, sy: number, sz: number,
  m: Material,
): Mesh => {
  const x0 = cx - sx / 2, x1 = cx + sx / 2;
  const y0 = cy - sy / 2, y1 = cy + sy / 2;
  const z0 = cz - sz / 2, z1 = cz + sz / 2;
  const v: Vec3[] = [
    [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
    [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
  ];
  const q = (a: number, b: number, c: number, d: number): Face[] => [
    { a, b, c, m }, { a, b: c, c: d, m },
  ];
  return {
    v,
    f: [
      ...q(0, 1, 2, 3), // -z
      ...q(5, 4, 7, 6), // +z
      ...q(4, 0, 3, 7), // -x
      ...q(1, 5, 6, 2), // +x
      ...q(3, 2, 6, 7), // +y
      ...q(4, 5, 1, 0), // -y
    ],
  };
};

export const plane = (
  cx: number, cy: number, cz: number,
  sx: number, sz: number,
  m: Material,
  tiles = 1,
): Mesh => {
  const v: Vec3[] = [];
  const f: Face[] = [];
  for (let iz = 0; iz < tiles; iz++) {
    for (let ix = 0; ix < tiles; ix++) {
      const x0 = cx - sx / 2 + (sx / tiles) * ix;
      const x1 = x0 + sx / tiles;
      const z0 = cz - sz / 2 + (sz / tiles) * iz;
      const z1 = z0 + sz / tiles;
      const base = v.length;
      v.push([x0, cy, z0], [x1, cy, z0], [x1, cy, z1], [x0, cy, z1]);
      f.push({ a: base, b: base + 1, c: base + 2, m }, { a: base, b: base + 2, c: base + 3, m });
    }
  }
  return { v, f };
};

/** Cylinder (wafer, lens barrel, pipe). */
export const cylinder = (
  cx: number, cy: number, cz: number,
  radius: number, height: number,
  m: Material,
  seg = 48,
  caps = true,
): Mesh => {
  const v: Vec3[] = [];
  const f: Face[] = [];
  for (let i = 0; i < seg; i++) {
    const a = (i / seg) * Math.PI * 2;
    const x = Math.cos(a) * radius;
    const z = Math.sin(a) * radius;
    v.push([cx + x, cy, cz + z], [cx + x, cy + height, cz + z]);
  }
  for (let i = 0; i < seg; i++) {
    const a0 = i * 2;
    const a1 = ((i + 1) % seg) * 2;
    f.push({ a: a0, b: a0 + 1, c: a1 + 1, m }, { a: a0, b: a1 + 1, c: a1, m });
  }
  if (caps) {
    const topCenter = v.length;
    v.push([cx, cy + height, cz]);
    const bottomCenter = v.length;
    v.push([cx, cy, cz]);
    for (let i = 0; i < seg; i++) {
      const a0 = i * 2;
      const a1 = ((i + 1) % seg) * 2;
      f.push({ a: topCenter, b: a0 + 1, c: a1 + 1, m });
      f.push({ a: bottomCenter, b: a1, c: a0, m });
    }
  }
  return { v, f };
};

/** Transform helper: compose translate + euler + scale. */
export function xform(
  pos: Vec3 = [0, 0, 0],
  rot: Vec3 = [0, 0, 0],
  scale: number | Vec3 = 1,
): (v: Vec3) => Vec3 {
  const [rx, ry, rz] = rot;
  const sc: Vec3 = typeof scale === 'number' ? [scale, scale, scale] : scale;
  const cx = Math.cos(rx), sx = Math.sin(rx);
  const cy = Math.cos(ry), sy = Math.sin(ry);
  const cz = Math.cos(rz), sz = Math.sin(rz);
  return (v: Vec3): Vec3 => {
    let x = v[0] * sc[0], y = v[1] * sc[1], z = v[2] * sc[2];
    let t = y * cx - z * sx;
    z = y * sx + z * cx;
    y = t;
    t = x * cy + z * sy;
    z = -x * sy + z * cy;
    x = t;
    t = x * cz - y * sz;
    y = x * sz + y * cz;
    x = t;
    return [x + pos[0], y + pos[1], z + pos[2]];
  };
}

export { mat4, multiply, sub, norm };
