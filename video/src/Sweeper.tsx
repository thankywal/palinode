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
 * The run nobody had any reason to look at.
 *
 * Sentinel reads the shape of a run while it is happening, and in the moment
 * the only alarming shape is an irreversible action where there should not be
 * one. This run has no shape at all: every action ordinary, nothing
 * irreversible, and a score of zero that is entirely correct at the time.
 *
 * Then a fact turns up three weeks later, and the same ledger reads
 * differently. The four beats here are the four states that were actually
 * observed against the deployed service, in order, with the score the API
 * returned at each one.
 */

const Beat: React.FC<{
  at: number;
  when: string;
  title: string;
  body: string;
  value: string;
  tone: string;
  last?: boolean;
}> = ({at, when, title, body, value, tone, last}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: frame - at, fps, config: {damping: 200}});

  return (
    <div
      style={{
        display: 'flex',
        gap: 30,
        opacity: enter,
        transform: `translateX(${interpolate(enter, [0, 1], [-22, 0])}px)`,
      }}
    >
      {/* The spine. It stops at the last beat rather than running off. */}
      <div style={{width: 3, position: 'relative', flexShrink: 0}}>
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: last ? 'transparent' : 'rgba(255,255,255,.14)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: -8,
            top: 26,
            width: 19,
            height: 19,
            borderRadius: 10,
            background: theme.bg,
            border: `3px solid ${tone}`,
          }}
        />
      </div>

      <div style={{flex: 1, paddingBottom: last ? 0 : 8}}>
        <div
          style={{
            fontFamily: mono,
            fontSize: 16,
            letterSpacing: 1.6,
            color: theme.dim,
            textTransform: 'uppercase',
          }}
        >
          {when}
        </div>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 20, marginTop: 6}}>
          <div style={{fontSize: 36, fontWeight: 800, letterSpacing: -0.5}}>{title}</div>
          <div
            style={{
              marginLeft: 'auto',
              fontFamily: mono,
              fontSize: 30,
              fontWeight: 800,
              color: tone,
              whiteSpace: 'nowrap',
            }}
          >
            {value}
          </div>
        </div>
        <div style={{fontSize: 23, color: theme.dim, marginTop: 9, lineHeight: 1.5}}>
          {body}
        </div>
      </div>
    </div>
  );
};

export const Sweeper: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const {beats} = timing.sweeper;

  const head = spring({frame, fps, config: {damping: 200}});
  const out = interpolate(
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
          padding: '54px 110px 48px',
          opacity: out,
        }}
      >
        <div style={{opacity: head}}>
          <div
            style={{
              fontSize: 15,
              letterSpacing: 5,
              fontWeight: 700,
              color: theme.violet,
              textTransform: 'uppercase',
            }}
          >
            The other kind of incident
          </div>
          <div style={{fontSize: 40, fontWeight: 800, letterSpacing: -1, marginTop: 6}}>
            Nothing about the run changed. What changed is what we know.
          </div>
        </div>

        <div style={{marginTop: 44, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly'}}>
          <Beat
            at={beats[0]}
            when="23 days ago"
            title="A vendor renewal runs"
            body="A database write, a merged config, an email, a card charge. Every action ordinary. Nothing irreversible anywhere in it."
            value="4 actions"
            tone={theme.sky}
          />
          <Beat
            at={beats[1]}
            when="At the time"
            title="Sentinel scores it"
            body="No unknown beneficiary, no irreversible tail, no missing reversal path. There is nothing here to be alarmed about, and it says so."
            value="0.00"
            tone={theme.green}
          />
          <Beat
            at={beats[2]}
            when="Today"
            title="The acquiring bank reports the vendor"
            body="One fact, arriving late, into the intel store. The ledger is untouched. Every action in it is exactly what it was."
            value="+1.20"
            tone={theme.amber}
          />
          <Beat
            at={beats[3]}
            when="On the hour"
            title="Cloud Scheduler wakes the Sweeper"
            body="No request in flight. Nobody waiting for an answer. It reads the same run again, clears the threshold, and takes it back."
            value="reversed"
            tone={theme.red}
            last
          />
        </div>
      </AbsoluteFill>
    </Backdrop>
  );
};
