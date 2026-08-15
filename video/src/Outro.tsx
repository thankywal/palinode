import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Backdrop} from './Backdrop';
import {E, lerp, seg} from './shotcraft/Motion';
import {font, mono, theme} from './theme';
import timing from './timing.json';

/**
 * The close, in four beats, each one the picture for its own line.
 *
 * It has been wrong twice. First it was a single card of recovery statistics
 * held under the whole close, so the voice spent six seconds saying what
 * Palinode is while the screen showed how many actions came back. Then it was
 * two beats that ended on the words "cannot be taken back", which is a good
 * sentence and a bad ending: it stops rather than lands, and somebody watching
 * said so.
 *
 * Now it goes somewhere after that. The three defects, the wordmark, the
 * number that says this is not hypothetical, and then the only line in the
 * film that asks anything of the viewer.
 *
 * The counter is `odometer-digit-roll` from video-shotcraft, Apache 2.0: each
 * digit is its own reel, they settle left to right with an overshoot, and the
 * whole thing pulses once when the last one locks.
 */

const Found: React.FC<{at: number; where: string; what: string}> = ({
  at,
  where,
  what,
}) => {
  const frame = useCurrentFrame();
  const enter = seg(frame - at, 0, 14, E.outCubic);

  return (
    <div
      style={{
        display: 'flex',
        gap: 26,
        alignItems: 'baseline',
        padding: '17px 0',
        borderTop: '1px solid rgba(255,255,255,.09)',
        opacity: enter,
        transform: `translateY(${lerp(enter, 14, 0)}px)`,
      }}
    >
      <div
        style={{
          fontFamily: mono,
          fontSize: 22,
          fontWeight: 700,
          color: theme.sky,
          width: 132,
          flexShrink: 0,
        }}
      >
        {where}
      </div>
      <div style={{fontSize: 26, lineHeight: 1.45}}>{what}</div>
    </div>
  );
};

/** One digit as a reel: the wrong numbers go past before the right one stops. */
const Reel: React.FC<{value: number; at: number; size: number}> = ({
  value,
  at,
  size,
}) => {
  const frame = useCurrentFrame();
  const p = seg(frame - at, 0, 22, E.outBack);
  const spins = 2;
  // Where the strip has to sit for `value` to be in the window.
  const target = spins * 10 + value;
  const offset = lerp(p, 0, target) % 10;
  const cell = size * 1.1;
  const blur = Math.min(7, Math.abs(1 - p) * 22);

  return (
    <span
      style={{
        display: 'inline-block',
        width: size * 0.62,
        height: cell,
        overflow: 'hidden',
        verticalAlign: 'top',
        position: 'relative',
      }}
    >
      <span
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: -offset * cell,
          filter: `blur(0px ${blur}px)`,
        }}
      >
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map((d, i) => (
          <span
            key={i}
            style={{
              display: 'block',
              height: cell,
              lineHeight: `${cell}px`,
              textAlign: 'center',
              fontFamily: mono,
              fontSize: size,
              fontWeight: 800,
            }}
          >
            {d}
          </span>
        ))}
      </span>
    </span>
  );
};

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const beats = timing.outro.beats;

  const stage = (i: number) => beats[i] ?? durationInFrames;

  // Each beat owns the frame until the next one takes it.
  const show = (i: number) => {
    const from = stage(i);
    const to = i + 1 < beats.length ? stage(i + 1) : durationInFrames;
    return seg(frame, from - 10, from + 6, E.outCubic) * (1 - seg(frame, to - 12, to + 2));
  };

  const mark = seg(frame - stage(1), 0, 20, E.outBack);
  const lock = seg(frame - (stage(2) + 26), 0, 10);

  const fadeOut = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [1, 0],
    {extrapolateLeft: 'clamp'}
  );

  return (
    <Backdrop>
      <AbsoluteFill
        style={{
          fontFamily: font,
          color: theme.text,
          padding: '0 120px',
          justifyContent: 'center',
          opacity: fadeOut,
        }}
      >
        {/* One: what broke when the systems became real. */}
        <div style={{opacity: show(0), position: 'absolute', left: 120, right: 120}}>
          <div
            style={{
              fontSize: 15,
              letterSpacing: 5,
              fontWeight: 700,
              color: theme.sky,
              textTransform: 'uppercase',
            }}
          >
            What connecting the real systems broke
          </div>
          <div
            style={{
              fontSize: 40,
              fontWeight: 800,
              letterSpacing: -1,
              marginTop: 8,
              marginBottom: 26,
            }}
          >
            Three things a simulator had been agreeing with
          </div>
          <Found
            at={stage(0) + 14}
            where="Stripe"
            what="The contract named the charge. Stripe named it something else, and the first live refund failed."
          />
          <Found
            at={stage(0) + 30}
            where="Stripe again"
            what="Search cannot see a charge made a second ago, so the reversal looked up nothing and reported success."
          />
          <Found
            at={stage(0) + 46}
            where="Slack"
            what="The delete quietly did nothing and returned ok. The message was still there when we opened the channel."
          />
        </div>

        {/* Two: the name. */}
        <div
          style={{
            opacity: show(1),
            transform: `scale(${lerp(mark, 0.96, 1)})`,
            position: 'absolute',
            left: 120,
            right: 120,
          }}
        >
          <div
            style={{
              fontSize: 17,
              letterSpacing: 7,
              fontWeight: 700,
              color: theme.sky,
              textTransform: 'uppercase',
            }}
          >
            Autonomous Agent Remediation
          </div>
          <div
            style={{
              fontSize: 128,
              fontWeight: 800,
              letterSpacing: -4,
              lineHeight: 1,
              marginTop: 14,
            }}
          >
            Palinode
          </div>
          <div
            style={{
              width: lerp(mark, 0, 150),
              height: 8,
              borderRadius: 4,
              background: theme.sky,
              margin: '26px 0 28px',
            }}
          />
          <div style={{fontSize: 34, color: theme.dim, lineHeight: 1.45, maxWidth: 1180}}>
            Not the agent that does the work.{' '}
            <span style={{color: theme.text, fontWeight: 700}}>
              The one that has to be right about what cannot be taken back.
            </span>
          </div>
        </div>

        {/* Three: the number, so none of this reads as hypothetical. */}
        <div
          style={{
            opacity: show(2),
            position: 'absolute',
            left: 120,
            right: 120,
            textAlign: 'center',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'center',
              color: lock > 0.5 ? theme.sky : theme.text,
              transform: `scale(${1 + 0.03 * lock * (1 - lock) * 4})`,
            }}
          >
            <Reel value={7} at={stage(2) + 4} size={210} />
            <Reel value={9} at={stage(2) + 12} size={210} />
            <span
              style={{
                fontFamily: mono,
                fontSize: 116,
                fontWeight: 800,
                marginLeft: 10,
                alignSelf: 'flex-start',
                marginTop: 34,
              }}
            >
              %
            </span>
          </div>
          <div style={{fontSize: 34, color: theme.dim, marginTop: 26, lineHeight: 1.45}}>
            of enterprises have already reversed something an agent did.
            <br />
            <span style={{color: theme.text}}>They did it by hand, at two in the morning.</span>
          </div>
          <div style={{fontSize: 19, color: theme.dim, marginTop: 30, fontFamily: mono}}>
            Kore.ai Agent Productivity Index, June 2026
          </div>
        </div>

        {/* Four: the only thing the film asks of anybody. */}
        <div
          style={{
            opacity: show(3),
            position: 'absolute',
            left: 120,
            right: 120,
          }}
        >
          <div style={{fontSize: 66, fontWeight: 800, letterSpacing: -1.6, lineHeight: 1.2}}>
            Your agents are already acting.
            <br />
            <span style={{color: theme.sky}}>This is what happens next.</span>
          </div>
          <div
            style={{
              display: 'flex',
              gap: 44,
              marginTop: 46,
              fontFamily: mono,
              fontSize: 22,
              color: theme.dim,
            }}
          >
            <span>github.com/thankywal/palinode</span>
            <span style={{color: theme.sky}}>
              palinode-173485225974.us-central1.run.app
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
