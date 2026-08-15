// Vendored from video-shotcraft, Apache License 2.0.
//   https://github.com/Vincentwei1021/video-shotcraft
//   Copyright the video-shotcraft authors. See ./LICENSE.
//
// Unmodified except for this header. Used here for the 2.5D camera over the
// console captures: the evidence in this film is other people's dashboards,
// and a page that is merely panned across reads as a screenshot while a page
// with a camera on it reads as a place.
//
// The layout-scale zoom trick in here is the reason it is worth vendoring
// rather than reimplementing. Scaling a 3D composited layer makes Chromium
// rasterise at layout size and upscale, which softens every glyph. Applying
// the magnification as CSS zoom rasterises at the enlarged size instead.

// origin: disney-animation-rule-skill implementation-patterns (scanned 2026-07-13, absorbed 2026-07-15)

/**
 * Motion-derived signal: sample a pure trajectory at frame±dt (central
 * difference) to get velocity, speed and heading. Drive stretch, smear,
 * blur or shake intensity from `speed`; normalize amplitude by subject
 * size. Works on any pure `posAt` — no per-frame state.
 */
export const velocityAt = (
  posAt: (f: number) => { x: number; y: number },
  frame: number,
  dt = 0.5,
): { vx: number; vy: number; speed: number; direction: number } => {
  const before = posAt(frame - dt);
  const after = posAt(frame + dt);
  const vx = (after.x - before.x) / (2 * dt);
  const vy = (after.y - before.y) / (2 * dt);
  return { vx, vy, speed: Math.hypot(vx, vy), direction: Math.atan2(vy, vx) };
};

/**
 * Follow-through without stateful simulation: a trailing layer is just the
 * primary state sampled at `frame − delayFrames`. Build drag hierarchies by
 * giving each attachment a larger delay and a smaller amplitude (shadow 2f,
 * ghost 4f, …). Never accumulate state across rendered frames — every layer
 * stays a pure function of the frame number.
 */
export const lagged = <T>(
  stateAt: (f: number) => T,
  frame: number,
  delayFrames: number,
): T => stateAt(frame - delayFrames);

/**
 * Closed-form damped oscillation for recoil/settle tails, t in frames from
 * impact. Returns a signed offset factor decaying to 0; scale by the desired
 * peak amplitude. freq in cycles/frame (~0.1), damping per frame (~0.15).
 */
export const dampedSettle = (t: number, freq: number, damping: number): number =>
  t <= 0 ? 0 : Math.exp(-damping * t) * Math.sin(2 * Math.PI * freq * t);
