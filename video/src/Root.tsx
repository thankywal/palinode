import React from 'react';
import {Composition} from 'remotion';
import {Chapter, ChapterProps} from './Chapter';
import {Invoices} from './Invoices';
import {Sweeper} from './Sweeper';
import {ConsoleShot} from './ConsoleShot';
import {CONSOLE_SHOTS} from './consoleShots';
import {Intro} from './Intro';
import {Outro} from './Outro';
import {FPS, theme} from './theme';
import timing from './timing.json';

/**
 * Title cards only.
 *
 * Every duration here is read from timing.json, which plan.py derives from the
 * measured length of the narration. A card that runs a second longer than the
 * line over it is a card the voice is fighting.
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
      durationInFrames={timing.intro.durationInFrames}
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
      id="Invoices"
      component={Invoices}
      durationInFrames={timing.invoices.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />

    <Composition
      id="Sweeper"
      component={Sweeper}
      durationInFrames={timing.sweeper.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />

    <Composition
      id="Outro"
      component={Outro}
      durationInFrames={timing.outro.durationInFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />
    {Object.entries(CONSOLE_SHOTS).map(([name, props]) => (
      <Composition
        key={name}
        id={`shot-${name}`}
        component={ConsoleShot}
        durationInFrames={(timing.shots as Record<string, number>)[name] ?? 150}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={props}
      />
    ))}
  </>
);
