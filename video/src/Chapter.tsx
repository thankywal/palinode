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
 * Two second card that sits between segments of the screen recording.
 *
 * Deliberately short. These exist to give the recording structure, not to
 * replace it, and the rules ask for a live unedited demonstration.
 */

export type ChapterProps = {
  index: string;
  title: string;
  subtitle: string;
  accent: string;
};

export const Chapter: React.FC<ChapterProps> = ({
  index,
  title,
  subtitle,
  accent,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 200}});
  const x = interpolate(enter, [0, 1], [-40, 0]);
  const barHeight = interpolate(enter, [0, 1], [0, 132]);

  const out = interpolate(
    frame,
    [durationInFrames - 10, durationInFrames],
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
          opacity: out,
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: 40,
            alignItems: 'center',
            transform: `translateX(${x}px)`,
            opacity: enter,
          }}
        >
          <div style={{width: 8, height: barHeight, background: accent, borderRadius: 4}} />
          <div>
            <div
              style={{
                fontFamily: mono,
                fontSize: 22,
                letterSpacing: 4,
                color: accent,
                fontWeight: 700,
              }}
            >
              {index}
            </div>
            <div
              style={{
                fontSize: 82,
                fontWeight: 800,
                letterSpacing: -2,
                color: theme.text,
                marginTop: 10,
                lineHeight: 1.05,
              }}
            >
              {title}
            </div>
            <div style={{fontSize: 34, color: theme.dim, marginTop: 16, maxWidth: 1100}}>
              {subtitle}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
