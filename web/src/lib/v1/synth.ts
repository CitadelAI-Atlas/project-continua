// Web Audio synthesis for the v1 vocabulary.
// Renders symbols directly via WebAudio nodes; no pre-recorded WAVs.
// Matches the Python encoder in continua/encoder.py: linear sweep,
// pulse train with shaped spacing, attack/release envelopes.

import type { Symbol } from "./vocabulary";

const AMPLITUDE = 0.6;

function makeContext(): AudioContext {
  const AC = (window as unknown as {
    AudioContext: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  }).AudioContext ?? (window as unknown as {
    webkitAudioContext: typeof AudioContext;
  }).webkitAudioContext;
  const ctx = new AC();
  // iOS Safari starts every AudioContext in the "suspended" state and only
  // transitions to "running" after an explicit resume() call from within a
  // user gesture. Since playSymbol is always invoked from a click handler,
  // the resume here lands inside that gesture. No-op on browsers where the
  // context starts running. Without this, v1/v2 dashboards are silent on
  // mobile while desktop browsers play normally.
  void ctx.resume().catch(() => undefined);
  return ctx;
}

function applyEnvelope(
  gain: GainNode,
  startTime: number,
  durationS: number,
  ctx: AudioContext,
  attackMs = 8,
  releaseMs = 30,
) {
  const attack = attackMs / 1000;
  const release = releaseMs / 1000;
  const peak = AMPLITUDE;
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(peak, startTime + attack);
  gain.gain.setValueAtTime(peak, startTime + Math.max(0, durationS - release));
  gain.gain.linearRampToValueAtTime(0, startTime + durationS);
}

function scheduleSteady(
  ctx: AudioContext,
  destination: AudioNode,
  hz: number,
  startTime: number,
  durationS: number,
) {
  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(hz, startTime);
  const gain = ctx.createGain();
  applyEnvelope(gain, startTime, durationS, ctx);
  osc.connect(gain);
  gain.connect(destination);
  osc.start(startTime);
  osc.stop(startTime + durationS + 0.01);
}

function scheduleSweep(
  ctx: AudioContext,
  destination: AudioNode,
  startHz: number,
  endHz: number,
  startTime: number,
  durationS: number,
) {
  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(startHz, startTime);
  osc.frequency.linearRampToValueAtTime(endHz, startTime + durationS);
  const gain = ctx.createGain();
  applyEnvelope(gain, startTime, durationS, ctx);
  osc.connect(gain);
  gain.connect(destination);
  osc.start(startTime);
  osc.stop(startTime + durationS + 0.01);
}

function pulseStartTimes(
  pulseCount: number,
  durationS: number,
  accelerate: number,
): number[] {
  if (pulseCount === 1) return [0];
  let exponent = 1.0 + 1.5 * accelerate;
  if (exponent < 0.25) exponent = 0.25;
  const usable = durationS * 0.85;
  const starts: number[] = [];
  for (let i = 0; i < pulseCount; i++) {
    const normalized = i / (pulseCount - 1);
    starts.push(Math.pow(normalized, exponent) * usable);
  }
  return starts;
}

function schedulePulses(
  ctx: AudioContext,
  destination: AudioNode,
  durationS: number,
  pulseCount: number,
  baseHz: number,
  pulseHzs: number[] | undefined,
  accelerate: number,
  startTime: number,
) {
  const starts = pulseStartTimes(pulseCount, durationS, accelerate);
  const pulseDuration = Math.min(0.18, durationS / (pulseCount + 1));
  for (let i = 0; i < starts.length; i++) {
    const hz = pulseHzs ? pulseHzs[i % pulseHzs.length] : baseHz;
    scheduleSteady(ctx, destination, hz, startTime + starts[i], pulseDuration);
  }
}

export function playSymbol(symbol: Symbol): Promise<void> {
  return new Promise((resolve) => {
    const ctx = makeContext();
    const dest = ctx.destination;
    const t0 = ctx.currentTime + 0.05; // small lead-in
    const totalDuration = symbol.durationS;

    if (symbol.waveType === "steady") {
      scheduleSteady(ctx, dest, symbol.baseHz, t0, symbol.durationS);
    } else if (symbol.waveType === "sweep") {
      if (symbol.endHz === undefined) {
        throw new Error(`${symbol.name}: sweep requires endHz`);
      }
      scheduleSweep(ctx, dest, symbol.baseHz, symbol.endHz, t0, symbol.durationS);
    } else if (symbol.waveType === "pulses") {
      schedulePulses(
        ctx,
        dest,
        symbol.durationS,
        symbol.pulseCount ?? 1,
        symbol.baseHz,
        symbol.pulseHzs,
        symbol.accelerate ?? 0,
        t0,
      );
    }

    // Resolve when playback finishes plus a tail buffer
    const wallClockMs = (totalDuration + 0.2) * 1000;
    setTimeout(() => {
      void ctx.close().catch(() => undefined);
      resolve();
    }, wallClockMs);
  });
}
