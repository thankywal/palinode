import React from 'react';
import {useCurrentFrame} from 'remotion';
import {E, lerp, seg} from './shotcraft/Motion';
import {mono} from './theme';

/**
 * The moment the document is read, made visible.
 *
 * This is `scanline-annotate-focus` from video-shotcraft: a line sweeps down
 * the page at a constant rate, and each region it crosses gets framed by four
 * corner brackets that snap in from about 1.75 times size with a small
 * overshoot, then named in mono beside them. A status line counts what has
 * been found. The shot card is Apache 2.0, this implementation is ours, and
 * the easing vocabulary comes from src/shotcraft/Motion.tsx.
 *
 * Two rules from the card that matter more than the look. The page underneath
 * must not move, or the audience cannot tell whether it is being read or
 * merely loading. And a region must be framed strictly after the line has
 * passed it, never before, or the whole thing reads as choreography rather
 * than as a machine working.
 *
 * The regions are the fields Gemini actually returned for these two documents,
 * measured off the rendered pages rather than placed by eye. Framing something
 * the model did not report would make this an illustration.
 */

export type ScanTarget = {
  /** Fractions of the page, because the page is drawn at whatever size fits. */
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  /** Where the label goes. Below the box by default. */
  side?: 'above' | 'left';
};

const ARM = 14;

// Dark, because the thing being read is a piece of paper. The card these are
// drawn from frames dark UI and uses white brackets, and white brackets on a
// cream page are invisible, which took one render to discover.
const BORDER = '2.5px solid rgba(23,45,120,.95)';
const CORNERS: React.CSSProperties[] = [
  {left: 0, top: 0, borderTop: BORDER, borderLeft: BORDER},
  {right: 0, top: 0, borderTop: BORDER, borderRight: BORDER},
  {left: 0, bottom: 0, borderBottom: BORDER, borderLeft: BORDER},
  {right: 0, bottom: 0, borderBottom: BORDER, borderRight: BORDER},
];

export const ScanRead: React.FC<{
  from: number;
  to: number;
  targets: ScanTarget[];
  accent: string;
  accentRgb: string;
}> = ({from, to, targets, accent, accentRgb}) => {
  const frame = useCurrentFrame();
  const t = (frame - from) / Math.max(1, to - from);
  if (t <= 0) return null;

  // The line runs at a constant rate. No easing: a scan that slows down looks
  // like it found something difficult.
  const lineY = lerp(seg(t, 0.05, 0.78), -6, 108);
  const lineOn = seg(t, 0.03, 0.09) * (1 - seg(t, 0.78, 0.86));

  // Each region fires when the line clears its lower edge, then a minimum gap
  // so two boxes never snap on the same frame.
  const fireAt: number[] = [];
  let prev = -1;
  targets
    .map((tg, i) => ({i, bottom: tg.y + tg.h}))
    .sort((a, b) => a.bottom - b.bottom)
    .forEach(({i, bottom}) => {
      const raw = 0.05 + ((bottom * 100 + 6) / 114) * 0.73;
      const at = Math.max(raw, prev + 0.06);
      fireAt[i] = at;
      prev = at;
    });

  const found = targets.reduce((n, _, i) => n + (t >= fireAt[i] ? 1 : 0), 0);
  const complete = t > 0.84;

  return (
    <>
      {targets.map((tg, i) => {
        const ft = fireAt[i];
        const a = seg(t, ft, ft + 0.09, E.outCubic);
        if (a <= 0) return null;
        const snap = lerp(E.outBack(seg(t, ft, ft + 0.12)), 1.75, 1);
        const flash =
          0.14 * seg(t, ft + 0.03, ft + 0.07) * (1 - seg(t, ft + 0.07, ft + 0.2));
        const la = seg(t, ft + 0.04, ft + 0.14, E.outCubic);

        return (
          <React.Fragment key={i}>
            <div
              style={{
                position: 'absolute',
                left: `${tg.x * 100}%`,
                top: `${tg.y * 100}%`,
                width: `${tg.w * 100}%`,
                height: `${tg.h * 100}%`,
                opacity: Math.min(1, a * 1.6),
                transform: `scale(${snap})`,
              }}
            >
              {CORNERS.map((c, k) => (
                <div
                  key={k}
                  style={{
                    position: 'absolute',
                    width: ARM,
                    height: ARM,
                    filter: 'drop-shadow(0 0 3px rgba(255,255,255,.9))',
                    ...c,
                  }}
                />
              ))}
              <div
                style={{
                  position: 'absolute',
                  inset: 1,
                  background: accent,
                  opacity: flash,
                }}
              />
            </div>
            <div
              style={{
                position: 'absolute',
                left: tg.side === 'left' ? '6%' : `${tg.x * 100}%`,
                top: `${
                  (tg.side === 'above'
                    ? tg.y
                    : tg.side === 'left'
                    ? tg.y + tg.h / 2
                    : tg.y + tg.h) * 100
                }%`,
                marginTop: tg.side === 'above' ? -22 : tg.side === 'left' ? -9 : 6,
                fontFamily: mono,
                fontSize: 13,
                letterSpacing: 1.4,
                fontWeight: 700,
                color: accent,
                whiteSpace: 'nowrap',
                opacity: la,
                transform: `translateY(${lerp(la, 5, 0)}px)`,
                textShadow: '0 1px 6px rgba(255,255,255,.9)',
              }}
            >
              {tg.label}
            </div>
          </React.Fragment>
        );
      })}

      {/* The line, with the light that falls ahead of it. */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: `${lineY}%`,
          height: 46,
          marginTop: -46,
          background: `linear-gradient(180deg, transparent, rgba(${accentRgb},.10) 60%, rgba(${accentRgb},.03) 96%, transparent)`,
          opacity: lineOn,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 2,
            background: 'rgba(255,255,255,.95)',
            boxShadow: `0 0 10px ${accent}, 0 0 26px rgba(${accentRgb},.5)`,
          }}
        />
      </div>

      {/* What has been found so far, in the corner of the page. */}
      <div
        style={{
          position: 'absolute',
          right: 10,
          top: 8,
          fontFamily: mono,
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: 1.8,
          color: complete ? accent : '#5A6472',
          background: 'rgba(255,255,255,.86)',
          padding: '3px 8px',
          borderRadius: 4,
          opacity: seg(t, 0.02, 0.07),
        }}
      >
        {complete ? 'READ · COMPLETE' : `SCAN · 0${found}/0${targets.length}`}
      </div>
    </>
  );
};
