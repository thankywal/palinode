import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PageCam, CamKey} from './shotcraft/PageCam';
import {handheld} from './shotcraft/shake';
import {font, mono, theme} from './theme';

/**
 * A console capture, with a camera on it.
 *
 * These shots are the proof. They used to be held absolutely still, then
 * given a linear pan in ffmpeg, and both read as what they were: a slide.
 * The evidence in this film is other people's dashboards, and a page that is
 * merely translated across the frame looks like a screenshot, while a page
 * with a camera over it looks like somewhere you are standing.
 *
 * So the capture is full bleed and PageCam moves over it, starting slightly
 * oblique and squaring up as the line lands. The title does not move with it.
 * A caption that drifts with the camera reads as part of the page, and this
 * caption is ours while the page is not.
 *
 * PageCam and the handheld noise are vendored from video-shotcraft under
 * Apache 2.0. See src/shotcraft/LICENSE.
 */

export type ConsoleShotProps = {
  file: string;
  group: string;
  index: string;
  title: string;
  caption: string;
  accent: string;
  /** Page point the camera settles on, in the texture's own CSS pixels. */
  focus: [number, number];
  /** Aspect of the capture, so the page height follows from the width. */
  aspect: number;
};

export const consoleShotSchema = null;

export const ConsoleShot: React.FC<ConsoleShotProps> = ({
  file,
  group,
  index,
  title,
  caption,
  accent,
  focus,
  aspect,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  // PageCam lays the texture out 1920 wide, so the page height is whatever
  // the capture's aspect makes it. The textures are 2x, which is what keeps
  // the glyphs sharp once the camera magnifies them.
  const pageH = Math.round(1920 / aspect);

  // The move. In slightly wide and a few degrees off square, out tight on
  // whatever the line is about, arriving square. Short shots get the same
  // journey at the same shape, because the timing comes from the narration
  // and some of these lines are three seconds and some are eleven.
  const end = durationInFrames;
  const [fx, fy] = focus;
  const keys: CamKey[] = [
    {frame: 0, cx: 960, cy: pageH / 2, zoom: 1.0, rotY: -3.2, rotX: 1.4, persp: 2600},
    {
      frame: Math.round(end * 0.55),
      cx: (960 + fx) / 2,
      cy: (pageH / 2 + fy) / 2,
      zoom: 1.13,
      rotY: -1.1,
      rotX: 0.5,
      persp: 2600,
    },
    {frame: end, cx: fx, cy: fy, zoom: 1.26, rotY: 0, rotX: 0, persp: 2600},
  ];

  // Deterministic drift, so the frame is never perfectly locked. Small: this
  // is a document being read, not footage being shot off a shoulder.
  const [sx, sy] = handheld(frame, 1.6);

  const enter = spring({frame, fps, config: {damping: 200}});
  const out = interpolate(frame, [end - 12, end], [1, 0], {extrapolateLeft: 'clamp'});

  return (
    <AbsoluteFill style={{backgroundColor: theme.bg, opacity: out}}>
      <AbsoluteFill
        style={{
          transform: `translate(${sx}px, ${sy}px) scale(${interpolate(
            enter,
            [0, 1],
            [1.04, 1]
          )})`,
          opacity: enter,
        }}
      >
        <PageCam
          src={`console/${file}`}
          pageH={pageH}
          keys={keys}
          ease={Easing.bezier(0.33, 0, 0.15, 1)}
        />
      </AbsoluteFill>

      {/* Two layers, and both are needed.
        *
        * A vignette, because a bright console page cut against the dark cards
        * either side of it reads as a flash, and because the corners of these
        * captures are chrome nobody is looking at.
        *
        * Then a solid band under the title. A gradient alone was not enough:
        * the console has its own header exactly where ours goes, and two
        * headers on top of each other is not a caption, it is a mess. */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(130% 105% at 50% 46%, rgba(11,16,32,0) 38%,' +
            ' rgba(11,16,32,.45) 78%, rgba(11,16,32,.86) 100%)',
          pointerEvents: 'none',
        }}
      />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(9,13,26,.97) 0%, rgba(9,13,26,.95) 52%,' +
            ' rgba(9,13,26,.72) 76%, rgba(9,13,26,0) 100%)',
          height: 268,
          pointerEvents: 'none',
        }}
      />

      <AbsoluteFill
        style={{
          fontFamily: font,
          color: theme.text,
          padding: '46px 70px',
          opacity: enter,
        }}
      >
        <div style={{display: 'flex', gap: 22}}>
          <div
            style={{
              width: 6,
              height: 128,
              borderRadius: 4,
              background: accent,
              transform: `scaleY(${enter})`,
              transformOrigin: 'top',
              flexShrink: 0,
            }}
          />
          <div style={{maxWidth: 1500}}>
            <div
              style={{
                fontFamily: mono,
                fontSize: 15,
                letterSpacing: 3.5,
                fontWeight: 700,
                color: accent,
              }}
            >
              {group} &nbsp;{index}
            </div>
            <div
              style={{fontSize: 46, fontWeight: 800, letterSpacing: -1, marginTop: 5, lineHeight: 1}}
            >
              {title}
            </div>
            <div
              style={{
                fontSize: 22,
                lineHeight: 1.4,
                color: '#A9BAD2',
                marginTop: 12,
                opacity: interpolate(enter, [0.4, 1], [0, 1], {extrapolateLeft: 'clamp'}),
              }}
            >
              {caption}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
