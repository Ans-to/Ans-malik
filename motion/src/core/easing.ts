/**
 * easing.ts — the vocabulary of motion.
 *
 * Motion design lives or dies on these curves: an exponential-out makes type
 * "snap", a back-out gives overshoot and weight, a critically damped spring
 * makes a camera settle instead of stopping dead.
 */

export type Ease = (t: number) => number;

export const linear: Ease = (t) => t;

export const easeInQuad: Ease = (t) => t * t;
export const easeOutQuad: Ease = (t) => 1 - (1 - t) * (1 - t);
export const easeInOutQuad: Ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

export const easeInCubic: Ease = (t) => t * t * t;
export const easeOutCubic: Ease = (t) => 1 - Math.pow(1 - t, 3);

export const easeOutQuart: Ease = (t) => 1 - Math.pow(1 - t, 4);

export const easeInOutCubic: Ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export const easeOutQuint: Ease = (t) => 1 - Math.pow(1 - t, 5);

export const easeInOutQuint: Ease = (t) => (t < 0.5 ? 16 * t ** 5 : 1 - Math.pow(-2 * t + 2, 5) / 2);

/** Exponential out — the classic "UI snap". Fast attack, long soft landing. */
export const easeOutExpo: Ease = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

export const easeInExpo: Ease = (t) => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10));

export const easeInOutExpo: Ease = (t) =>
  t === 0 ? 0 : t === 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2;

/** Overshoot then settle — gives objects weight when they land. */
export const easeOutBack = (s = 1.70158): Ease => (t) => {
  const c3 = s + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2);
};

export const easeInOutBack = (s = 1.70158): Ease => (t) => {
  const c2 = s * 1.525;
  return t < 0.5
    ? (Math.pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    : (Math.pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2;
};

/** Elastic out — used sparingly, on the single most important beat. */
export const easeOutElastic: Ease = (t) => {
  if (t === 0 || t === 1) return t;
  const c4 = (2 * Math.PI) / 3;
  return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
};

/**
 * Analytic damped spring response to a step input.
 * x(t) = 1 - e^(-ζωt)(cos(ωd t) + (ζω/ωd) sin(ωd t))
 * `damping` 1 = critically damped, < 1 overshoots, > 1 crawls.
 */
export const spring = (duration = 1, damping = 0.55, omega = 12): Ease => (t) => {
  const T = Math.max(1e-6, duration);
  const time = Math.min(t, 1) * T;
  const w0 = omega;
  const zeta = damping;
  const wd = w0 * Math.sqrt(Math.max(1e-6, 1 - zeta * zeta));
  const e = Math.exp(-zeta * w0 * time);
  const value = 1 - e * (Math.cos(wd * time) + ((zeta * w0) / wd) * Math.sin(wd * time));
  // fade the residual wobble to exactly 1 at the end so loops never pop
  return t >= 1 ? 1 : value;
};

/** CSS-style cubic-bezier(x1,y1,x2,y2) with a Newton-Raphson x-inversion. */
export function cubicBezier(x1: number, y1: number, x2: number, y2: number): Ease {
  const A = (a: number, b: number) => 1 - 3 * b + 3 * a;
  const B = (a: number, b: number) => 3 * b - 6 * a;
  const C = (a: number) => 3 * a;
  const calc = (t: number, a: number, b: number) => ((A(a, b) * t + B(a, b)) * t + C(a)) * t;
  const slope = (t: number, a: number, b: number) => 3 * A(a, b) * t * t + 2 * B(a, b) * t + C(a);

  return (x: number) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) {
      const d = slope(t, x1, x2);
      if (Math.abs(d) < 1e-6) break;
      const err = calc(t, x1, x2) - x;
      if (Math.abs(err) < 1e-7) break;
      t -= err / d;
    }
    return calc(t, y1, y2);
  };
}

/** Staggered delay for per-character / per-word choreography. */
export const stagger = (i: number, step: number, offset = 0): number => offset + i * step;
