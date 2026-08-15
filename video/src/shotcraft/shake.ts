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

// origin: 模板片源仓库 helpers
/**
 * Deterministic hand-held camera noise. Layered sines at incommensurate
 * frequencies read as organic drift; amplitude in world units.
 */
export const handheld = (frame: number, amp = 0.012): [number, number, number] => [
  amp * (Math.sin(frame * 0.31) + 0.6 * Math.sin(frame * 0.83 + 1.7)),
  amp * (Math.sin(frame * 0.47 + 0.9) + 0.5 * Math.sin(frame * 1.13 + 3.1)),
  0,
];
