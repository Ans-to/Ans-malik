import React from 'react';
import {CameraMotionBlur} from '@remotion/motion-blur';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {cameraDrift} from './design.js';

/** Wrap the whole scene for drift; enable blur when the scene contains fast motion. */
export function CinemaMotion({children, fastTransition = false}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const d = cameraDrift(frame / fps);
  const content = React.createElement('div', {style: {position: 'absolute', inset: 0, transform: `translate(${d.x * 100}%, ${d.y * 100}%) scale(${d.scale})`}}, children);
  return fastTransition ? React.createElement(CameraMotionBlur, {shutterAngle: 180, samples: 10}, content) : content;
}
