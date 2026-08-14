import React from 'react';
import {Composition} from 'remotion';
import {Chapter, ChapterProps} from './Chapter';
import {Intro} from './Intro';
import {Outro} from './Outro';
import {FPS, theme} from './theme';

/**
 * Title cards only.
 *
 * The demo itself is a screen recording of the real dashboard driving the real
 * control plane, because the rules ask for a live unedited demonstration and
 * an animated reconstruction of a product working is not that. These cards top
 * and tail it and mark the chapters.
 */
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Intro"
      component={Intro}
      durationInFrames={8 * FPS}
      fps={FPS}
      width={1920}
      height={1080}
    />

    <Composition
      id="Chapter"
      component={Chapter}
      durationInFrames={2 * FPS}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={
        {
          index: '01',
          title: 'The fleet does its job',
          subtitle: 'Three ADK agents, five real actions, one poisoned invoice.',
          accent: theme.sky,
        } satisfies ChapterProps
      }
    />

    <Composition
      id="Outro"
      component={Outro}
      durationInFrames={7 * FPS}
      fps={FPS}
      width={1920}
      height={1080}
    />
  </>
);
