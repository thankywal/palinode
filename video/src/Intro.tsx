import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Backdrop} from './Backdrop';
import {font, theme} from './theme';
import timing from './timing.json';

/**
 * The opening card.
 *
 * Judges watch a lot of these back to back. The point of this card is that the
 * name explains itself before anyone has to be told what the product does.
 *
 * The beats are read from timing.json rather than chosen. The quote used to
 * hand off to the wordmark at frame 128 because eight seconds felt right, and
 * the voice was still saying to take back what an earlier poem said while the
 * words it was reading had already gone.
 */

const Line: React.FC<{
  at: number;
  children: React.ReactNode;
  size: number;
  colour?: string;
  weight?: number;
}> = ({at, children, size, colour = theme.text, weight = 500}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame: frame - at, fps, config: {damping: 200}});
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const y = interpolate(enter, [0, 1], [22, 0]);

  return (
    <div
      style={{
        fontSize: size,
        color: colour,
        fontWeight: weight,
        lineHeight: 1.35,
        opacity,
        transform: `translateY(${y}px)`,
        letterSpacing: -0.4,
      }}
    >
      {children}
    </div>
  );
};

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  // The quote fades out as the wordmark takes over.
  const {second, handoff: hand} = timing.intro;
  const handoff = interpolate(frame, [hand - 10, hand + 8], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const markIn = spring({frame: frame - hand, fps, config: {damping: 200}});
  const markScale = interpolate(markIn, [0, 1], [0.94, 1]);
  const ruleWidth = interpolate(markIn, [0, 1], [0, 150]);

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
          padding: '0 150px',
          opacity: fadeOut,
        }}
      >
        <div style={{opacity: handoff, position: 'absolute', left: 150, right: 150}}>
          <Line at={8} size={44} colour={theme.dim}>
            In classical poetry, a <span style={{color: theme.sky}}>palinode</span>
          </Line>
          <Line at={26} size={44} colour={theme.dim}>
            is a poem written for one purpose only:
          </Line>
          <div style={{height: 34}} />
          <Line at={second} size={62} weight={800}>
            to take back what an
          </Line>
          <Line at={second + 12} size={62} weight={800}>
            earlier poem said.
          </Line>
        </div>

        {/*
          The third line of the quote, this is a palinode for AI agents, is not
          written here. It is the moment the wordmark arrives, and the mark
          says it better than the sentence does.
        */}

        <div
          style={{
            opacity: markIn,
            transform: `scale(${markScale})`,
            position: 'absolute',
            left: 150,
          }}
        >
          <div
            style={{
              fontSize: 19,
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
              fontSize: 148,
              fontWeight: 800,
              letterSpacing: -4,
              color: theme.text,
              marginTop: 16,
              lineHeight: 1,
            }}
          >
            Palinode
          </div>
          <div
            style={{
              width: ruleWidth,
              height: 8,
              borderRadius: 4,
              background: theme.sky,
              marginTop: 30,
            }}
          />
          <div style={{fontSize: 40, color: theme.dim, marginTop: 32, fontWeight: 500}}>
            The agent fleet that{' '}
            <span style={{color: theme.text, fontWeight: 800}}>
              undoes what your other agents got wrong.
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
