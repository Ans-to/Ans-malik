import palettes from '../design_system/palettes.json' with {type: 'json'};

export const ease = 'cubic-bezier(0.16, 1, 0.3, 1)';
export const gsapEase = 'expo.out';
export function paletteVariables(name) {
  const palette = palettes[name];
  if (!palette || typeof palette !== 'object') throw new Error(`Unknown palette: ${name}`);
  return Object.fromEntries(Object.entries(palette).map(([key, value]) => [`--${key}`, value]));
}
// Time is in seconds; offset values are fractions of the viewport.
export function cameraDrift(time) {
  return {x: 0.003 * Math.sin(0.37 * time), y: 0.003 * Math.sin(0.29 * time + 1), scale: 1 + 0.003 * Math.sin(0.23 * time + 0.5)};
}
