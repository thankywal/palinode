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

/**
 * The closing card.
 *
 * The last number on screen is the one that cannot be recovered, on purpose.
 * A recovery tool that ends on a victory slide is lying about what recovery is.
 */

const Row: React.FC<{
  at: number;
  label: string;
  value: string;
  colour: string;
}> = ({at, label, value, colour}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: frame - at, fps, config: {damping: 200}});

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        padding: '22px 0',
        borderTop: `1px solid ${theme.line}`,
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [16, 0])}px)`,
      }}
    >
      <div style={{fontSize: 34, color: theme.dim}}>{label}</div>
      <div
        style={{
          fontSize: 58,
          fontWeight: 800,
          color: colour,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </div>
    </div>
  );
};

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const head = spring({frame, fps, config: {damping: 200}});
  const tail = spring({frame: frame - 130, fps, config: {damping: 200}});
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 14, durationInFrames],
    [1, 0],
    {extrapolateLeft: 'clamp'}
  );

  return (
    <Backdrop>
      <AbsoluteFill
        style={{
          fontFamily: font,
          color: theme.text,
          justifyContent: 'center',
          padding: '0 170px',
          opacity: fadeOut,
        }}
      >
        <div style={{opacity: head, transform: `translateY(${interpolate(head, [0, 1], [20, 0])}px)`}}>
          <div
            style={{
              fontSize: 19,
              letterSpacing: 7,
              fontWeight: 700,
              color: theme.sky,
              textTransform: 'uppercase',
            }}
          >
            One run, five actions
          </div>
          <div style={{fontSize: 76, fontWeight: 800, letterSpacing: -2, marginTop: 14}}>
            What came back
          </div>
        </div>

        <div style={{marginTop: 46}}>
          <Row at={22} label="Reversed" value="1" colour={theme.green} />
          <Row at={38} label="Compensated" value="3" colour={theme.amber} />
          <Row at={54} label="Unrecoverable" value="1" colour={theme.red} />
          <Row at={72} label="Exposure disclosed" value="$4,200.00" colour={theme.red} />
        </div>

        <div
          style={{
            marginTop: 54,
            opacity: tail,
            transform: `translateY(${interpolate(tail, [0, 1], [16, 0])}px)`,
          }}
        >
          <div style={{fontSize: 36, color: theme.text, lineHeight: 1.45, maxWidth: 1240}}>
            Where an action genuinely cannot be reversed,{' '}
            <span style={{color: theme.red, fontWeight: 700}}>Palinode does not pretend.</span>
          </div>
          <div
            style={{
              fontFamily: mono,
              fontSize: 26,
              color: theme.dim,
              marginTop: 34,
            }}
          >
            github.com/thankywal/palinode
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
