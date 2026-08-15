import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {E, lerp, seg} from './shotcraft/Motion';
import {font, mono, theme} from './theme';

/**
 * The board, reviewed row by row, with a light that goes where the voice does.
 *
 * This is `dashboard-glow-highlight-pill` from video-shotcraft: a spot of
 * light travels across a dashboard, stretches into a capsule as it arrives,
 * and then draws the outline of the thing it has arrived at. The shot card is
 * Apache 2.0, this implementation is ours.
 *
 * It replaces the worst thirty five seconds of the film. The board is settled
 * by this point in the story and the previous cut slid a crop of it around
 * with a sine drift, which is a camera move over a photograph and reads
 * exactly like one. Somebody watching said it looked like fake motion, and
 * they were right: nothing in the frame was moving, so the frame moved.
 *
 * A light that arrives on the row being named is not a camera move at all. It
 * is the film pointing at something, which is what the narration is doing.
 *
 * The rows are measured off the captured frame, not placed by eye.
 */

export type Mark = {
  /** Box in 1920x1080 space, measured from the 4K capture. */
  x: number;
  y: number;
  w: number;
  h: number;
  /** Frame this mark is named on, relative to the shot. */
  at: number;
  tone: string;
  /**
   * Only where the board does not already say it. Every ledger row carries
   * its own state badge, so labelling them again put our word on top of the
   * recovery panel and told the audience nothing they could not read.
   */
  label?: string;
  labelSide?: 'left' | 'right';
};

// The ledger panel, not the whole board. Sampling a row across the full frame
// gave the board's extent and drew boxes over three columns at once.
const LEDGER_X = 504;
const LEDGER_W = 889;

/** The five ledger rows, halved from the 4K frame they were found in. */
export const ROWS = {
  db: {x: LEDGER_X, y: 163, w: LEDGER_W, h: 70},
  slack: {x: LEDGER_X, y: 246, w: LEDGER_W, h: 68},
  email: {x: LEDGER_X, y: 327, w: LEDGER_W, h: 67},
  stripe: {x: LEDGER_X, y: 407, w: LEDGER_W, h: 68},
  wire: {x: LEDGER_X, y: 486, w: LEDGER_W, h: 70},
  disclosure: {x: 1442, y: 747, w: 316, h: 272},
};

const Highlight: React.FC<{mark: Mark; frame: number}> = ({mark, frame}) => {
  const t = frame - mark.at;

  // Three stages of one light, which is the point of the card: a spot that
  // arrives, a capsule that gathers, an outline that is drawn from where the
  // capsule ended. Break any of them apart and it becomes three animations.
  const arrive = seg(t, -10, 4, E.outCubic);
  const gather = seg(t, 2, 12, E.outQuart);
  const draw = seg(t, 10, 26, E.outQuart);
  const hold = seg(t, 24, 34);
  if (arrive <= 0) return null;

  const cx = mark.x + mark.w / 2;
  const cy = mark.y + mark.h / 2;

  // The spot comes in from the right and flattens into the row.
  const spotX = lerp(arrive, mark.x + mark.w + 220, cx);
  const spotW = lerp(gather, 26, mark.w);
  const spotH = lerp(gather, 26, mark.h);

  return (
    <>
      {/* The travelling light, gone once the outline has it. */}
      <div
        style={{
          position: 'absolute',
          left: spotX - spotW / 2,
          top: cy - spotH / 2,
          width: spotW,
          height: spotH,
          borderRadius: spotH / 2,
          background: mark.tone,
          opacity: 0.5 * arrive * (1 - seg(t, 12, 20)),
          filter: `blur(${lerp(gather, 9, 16)}px)`,
          pointerEvents: 'none',
        }}
      />

      {/* The outline it hands over to, drawn from the middle outwards. */}
      <div
        style={{
          position: 'absolute',
          left: mark.x,
          top: mark.y,
          width: mark.w,
          height: mark.h,
          borderRadius: 12,
          border: `2px solid ${mark.tone}`,
          boxShadow: `0 0 ${lerp(hold, 34, 16)}px ${mark.tone}, inset 0 0 30px ${mark.tone}22`,
          opacity: draw,
          clipPath: `inset(0 ${lerp(draw, 50, 0)}% 0 ${lerp(draw, 50, 0)}% round 12px)`,
          pointerEvents: 'none',
        }}
      />

      {mark.label ? (
      <div
        style={{
          position: 'absolute',
          left: mark.labelSide === 'left' ? undefined : mark.x + mark.w + 18,
          right: mark.labelSide === 'left' ? 1920 - mark.x + 18 : undefined,
          top: cy - 15,
          textAlign: mark.labelSide === 'left' ? 'right' : 'left',
          fontFamily: mono,
          fontSize: 21,
          fontWeight: 700,
          letterSpacing: 1.6,
          color: mark.tone,
          whiteSpace: 'nowrap',
          opacity: seg(t, 16, 26, E.outCubic),
          transform: `translateX(${lerp(seg(t, 16, 26, E.outCubic), -14, 0)}px)`,
        }}
      >
        {mark.label}
      </div>
      ) : null}
    </>
  );
};

export const LedgerReview: React.FC<{
  marks: Mark[];
  title: string;
  kicker: string;
  accent: string;
  /** How far the frame closes in over the shot. Small: the board is evidence. */
  push?: number;
}> = ({marks, title, kicker, accent, push = 1.06}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const t = frame / Math.max(1, durationInFrames - 1);

  const head = seg(t, 0, 0.06, E.outCubic);
  const out = interpolate(frame, [durationInFrames - 12, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
  });

  // The board itself is dimmed a little so a light on it can read as light.
  const dim = seg(t, 0, 0.12) * 0.28;

  return (
    <AbsoluteFill style={{backgroundColor: theme.bg, opacity: out}}>
      <AbsoluteFill
        style={{
          transform: `scale(${lerp(seg(t, 0, 1, E.inOutQuad), 1, push)})`,
          transformOrigin: '52% 34%',
        }}
      >
        <Img src={staticFile('board.png')} style={{width: 1920, height: 1080}} />
        <AbsoluteFill style={{background: `rgba(4,7,16,${dim})`}} />
        {marks.map((m, i) => (
          <Highlight key={i} mark={m} frame={frame} />
        ))}
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(6,10,22,.96) 0%, rgba(6,10,22,.9) 55%,' +
            ' rgba(6,10,22,0) 100%)',
          height: 172,
          pointerEvents: 'none',
        }}
      />

      <AbsoluteFill
        style={{
          fontFamily: font,
          color: theme.text,
          padding: '34px 64px',
          pointerEvents: 'none',
          opacity: head,
        }}
      >
        <div style={{display: 'flex', alignItems: 'flex-end', gap: 20}}>
          <div style={{width: 6, height: 58, borderRadius: 4, background: accent}} />
          <div>
            <div
              style={{
                fontFamily: mono,
                fontSize: 15,
                letterSpacing: 3.5,
                fontWeight: 700,
                color: accent,
                textTransform: 'uppercase',
              }}
            >
              {kicker}
            </div>
            <div style={{fontSize: 42, fontWeight: 800, letterSpacing: -1, marginTop: 5}}>
              {title}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
