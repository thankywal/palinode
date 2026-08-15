import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Backdrop} from './Backdrop';
import {font, mono, theme} from './theme';
import timing from './timing.json';

/**
 * The close, in two beats, and each one is the picture for its own line.
 *
 * It used to be one card of recovery statistics held under both lines, which
 * meant the voice spent the last six seconds saying what Palinode is while the
 * screen showed how many actions came back. It read as if the film had stopped
 * halfway through a thought, because it had.
 *
 * So the first line gets what it is actually about: the three defects that had
 * been sitting behind a simulator until something real disagreed. The second
 * gets the wordmark and somewhere to go.
 */

const Found: React.FC<{at: number; where: string; what: string}> = ({
  at,
  where,
  what,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: frame - at, fps, config: {damping: 200}});

  return (
    <div
      style={{
        display: 'flex',
        gap: 26,
        alignItems: 'baseline',
        padding: '17px 0',
        borderTop: '1px solid rgba(255,255,255,.09)',
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [14, 0])}px)`,
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

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const {second} = timing.outro;

  const head = spring({frame, fps, config: {damping: 200}});

  // The findings hand over to the wordmark on the second line, the way the
  // opening card hands the quote over to it.
  const handoff = interpolate(frame, [second - 12, second + 6], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const mark = spring({frame: frame - second, fps, config: {damping: 200}});

  const fadeOut = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
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
        <div style={{opacity: handoff, position: 'absolute', left: 120, right: 120}}>
          <div style={{opacity: head}}>
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
          </div>

          <Found
            at={14}
            where="Stripe"
            what="The contract named the charge. Stripe named it something else, and the first live refund failed."
          />
          <Found
            at={30}
            where="Stripe again"
            what="Search cannot see a charge made a second ago, so the reversal looked up nothing and reported success."
          />
          <Found
            at={46}
            where="Slack"
            what="The delete quietly did nothing and returned ok. The message was still there when we opened the channel."
          />
        </div>

        <div
          style={{
            opacity: mark,
            transform: `scale(${interpolate(mark, [0, 1], [0.96, 1])})`,
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
              width: interpolate(mark, [0, 1], [0, 150]),
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
          <div
            style={{
              display: 'flex',
              gap: 44,
              marginTop: 34,
              fontFamily: mono,
              fontSize: 21,
              color: theme.dim,
            }}
          >
            <span>github.com/thankywal/palinode</span>
            <span style={{color: theme.sky}}>palinode-173485225974.us-central1.run.app</span>
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
