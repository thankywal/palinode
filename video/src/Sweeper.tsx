import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Backdrop} from './Backdrop';
import {E, lerp, seg} from './shotcraft/Motion';
import {font, mono, theme} from './theme';
import timing from './timing.json';

/**
 * The run nobody had any reason to look at, as a journey along a timeline.
 *
 * This is `timeline-travel` from video-shotcraft: a camera that accelerates
 * along a horizontal axis, each tick popping up as it is passed, a hard stop
 * on the last one and a push in. The shot card is Apache 2.0, the
 * implementation here is ours, and the easing vocabulary comes from
 * src/shotcraft/Motion.tsx.
 *
 * It is the right shot for this because the argument is literally a journey
 * along a timeline. Sentinel reads the shape of a run while it happens, and
 * this run has no shape: every action ordinary, nothing irreversible, a score
 * of zero that was correct at the time. Three weeks of nothing, and then a
 * fact turns up and the same ledger reads differently. A vertical list said
 * all of that and none of it moved.
 *
 * The camera arrives at each tick on the frame its narration line starts, so
 * the journey is paced by the voice rather than by a travel curve.
 */

const AXIS_Y = 660;
const GAP = 1560;
const TICKS = [960, 960 + GAP, 960 + GAP * 2, 960 + GAP * 3];

type Beat = {
  when: string;
  title: string;
  body: string;
  value: string;
  tone: string;
};

const BEATS: Beat[] = [
  {
    when: '23 days ago',
    title: 'A vendor renewal runs',
    body: 'A database write, a merged config, an email, a card charge. Every action ordinary. Nothing irreversible anywhere in it.',
    value: '4 actions',
    tone: theme.sky,
  },
  {
    when: 'At the time',
    title: 'Sentinel scores it',
    body: 'No unknown beneficiary, no irreversible tail, no missing reversal path. Nothing here to be alarmed about, and it says so.',
    value: '0.00',
    tone: theme.green,
  },
  {
    when: 'Today',
    title: 'The bank reports the vendor',
    body: 'One fact, arriving late, into the intel store. The ledger is untouched. Every action in it is exactly what it was.',
    value: '+1.20',
    tone: theme.amber,
  },
  {
    when: 'On the hour',
    title: 'Cloud Scheduler wakes the Sweeper',
    body: 'No request in flight. Nobody waiting for an answer. It reads the same run again, clears the threshold, and takes it back.',
    value: 'reversed',
    tone: theme.red,
  },
];

const CARD_W = 1180;

const TickStop: React.FC<{i: number; at: number}> = ({i, at}) => {
  const frame = useCurrentFrame();
  const beat = BEATS[i];

  // Six frames early, so the card is standing by the time the camera is on it.
  const pop = spring({
    frame: frame - (at - 6),
    fps: 30,
    config: {damping: 11, stiffness: 160, mass: 0.9},
    durationInFrames: 26,
  });

  const rise = lerp(pop, 60, 0);
  const settle = lerp(pop, 0.9, 1);

  return (
    <div style={{position: 'absolute', left: TICKS[i], top: 0}}>
      {/* The tick itself, on the axis. */}
      <div
        style={{
          position: 'absolute',
          left: -4,
          top: AXIS_Y - 30,
          width: 8,
          height: 60,
          borderRadius: 4,
          background: beat.tone,
          opacity: Math.min(1, pop * 2),
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: -240,
          top: AXIS_Y + 48,
          width: 480,
          textAlign: 'center',
          fontFamily: mono,
          fontSize: 26,
          letterSpacing: 2.6,
          textTransform: 'uppercase',
          color: theme.dim,
          opacity: Math.min(1, pop * 1.6),
        }}
      >
        {beat.when}
      </div>

      {/* The card stands up out of the tick. */}
      <div
        style={{
          position: 'absolute',
          left: -CARD_W / 2,
          top: AXIS_Y - 30 - 330,
          width: CARD_W,
          opacity: Math.min(1, pop * 1.8),
          transform: `translateY(${rise}px) scale(${settle})`,
          transformOrigin: 'bottom center',
        }}
      >
        <div
          style={{
            border: `2px solid ${beat.tone}55`,
            background: 'rgba(255,255,255,.035)',
            borderRadius: 18,
            padding: '30px 34px',
            boxShadow: `0 30px 90px rgba(0,0,0,.5)`,
          }}
        >
          <div style={{display: 'flex', alignItems: 'baseline', gap: 24}}>
            <div style={{fontSize: 46, fontWeight: 800, letterSpacing: -0.8, flex: 1}}>
              {beat.title}
            </div>
            <div
              style={{
                fontFamily: mono,
                fontSize: 40,
                fontWeight: 800,
                color: beat.tone,
                whiteSpace: 'nowrap',
              }}
            >
              {beat.value}
            </div>
          </div>
          <div style={{fontSize: 27, color: theme.dim, marginTop: 14, lineHeight: 1.5}}>
            {beat.body}
          </div>
        </div>
      </div>
    </div>
  );
};

export const Sweeper: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const {beats} = timing.sweeper;

  // Hold, travel, hold. The camera sits on a tick for as long as its line is
  // being read, then crosses to the next one in about three quarters of a
  // second, arriving just before the next line starts.
  //
  // Easing the whole journey as one move was the first attempt and it was
  // wrong: the camera was somewhere between two ticks for most of the shot,
  // which meant most of the shot was empty axis.
  const TRAVEL = 22;
  const stops: number[] = [];
  const world: number[] = [];
  beats.forEach((b, i) => {
    const x = TICKS[i] - 960;
    const arrive = i === 0 ? b : b - 6;
    if (i > 0) {
      stops.push(Math.max(stops[stops.length - 1] + 1, arrive - TRAVEL));
      world.push(TICKS[i - 1] - 960);
    }
    stops.push(Math.max(arrive, (stops[stops.length - 1] ?? -1) + 1));
    world.push(x);
  });
  stops.push(durationInFrames);
  world.push(TICKS[TICKS.length - 1] - 960);

  const camX = interpolate(frame, stops, world, {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  // Hard stop, then push. The last tick is the one that matters and the shot
  // should arrive on it rather than drift past.
  const t = frame / Math.max(1, durationInFrames - 1);
  const push = lerp(seg(t, 0.86, 1, E.outCubic), 1, 1.1);

  const head = seg(t, 0, 0.06, E.outCubic);
  const out = interpolate(frame, [durationInFrames - 14, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
  });

  return (
    <Backdrop>
      <AbsoluteFill style={{fontFamily: font, color: theme.text, opacity: out}}>
        {/* The world. Only translate and scale move. */}
        <AbsoluteFill
          style={{
            transform: `scale(${push}) translateX(${-camX}px)`,
            transformOrigin: '960px 520px',
          }}
        >
          {/* The axis, running the length of the journey. */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: AXIS_Y,
              width: TICKS[3] + 1400,
              height: 3,
              background:
                'linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.22) 8%,' +
                ' rgba(255,255,255,.22) 92%, rgba(255,255,255,0))',
            }}
          />
          {BEATS.map((_, i) => (
            <TickStop key={i} i={i} at={beats[i]} />
          ))}
        </AbsoluteFill>

        {/* The title does not travel. */}
        <AbsoluteFill style={{padding: '54px 90px', pointerEvents: 'none'}}>
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
        </AbsoluteFill>
      </AbsoluteFill>
    </Backdrop>
  );
};
