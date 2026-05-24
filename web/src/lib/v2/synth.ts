// Web Audio synthesis for v2 primitives. Renders each wave kind in
// continua/encoder_v2.py with the same canonical parameters.

import type { Primitive } from "./vocabulary";

const AMPLITUDE = 0.55;

function makeContext(): AudioContext {
  const AC = (window as unknown as {
    AudioContext: typeof AudioContext;
    webkitAudioContext?: typeof AudioContext;
  }).AudioContext ?? (window as unknown as {
    webkitAudioContext: typeof AudioContext;
  }).webkitAudioContext;
  return new AC();
}

function applyEnvelope(
  gain: GainNode,
  startTime: number,
  durationS: number,
  peak = AMPLITUDE,
  attackMs = 10,
  releaseMs = 30,
) {
  const attack = attackMs / 1000;
  const release = releaseMs / 1000;
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(peak, startTime + attack);
  gain.gain.setValueAtTime(peak, startTime + Math.max(0, durationS - release));
  gain.gain.linearRampToValueAtTime(0, startTime + durationS);
}

function scheduleSine(
  ctx: AudioContext,
  dest: AudioNode,
  hz: number,
  startTime: number,
  durationS: number,
  peak = AMPLITUDE,
) {
  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(hz, startTime);
  const gain = ctx.createGain();
  applyEnvelope(gain, startTime, durationS, peak);
  osc.connect(gain);
  gain.connect(dest);
  osc.start(startTime);
  osc.stop(startTime + durationS + 0.01);
}

function scheduleGlissando(
  ctx: AudioContext,
  dest: AudioNode,
  startHz: number,
  endHz: number,
  startTime: number,
  durationS: number,
  peak = AMPLITUDE,
) {
  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(startHz, startTime);
  // Exponential ramp is more perceptually linear for pitch
  osc.frequency.exponentialRampToValueAtTime(Math.max(20, endHz), startTime + durationS);
  const gain = ctx.createGain();
  applyEnvelope(gain, startTime, durationS, peak);
  osc.connect(gain);
  gain.connect(dest);
  osc.start(startTime);
  osc.stop(startTime + durationS + 0.01);
}

export function playPrimitive(p: Primitive): Promise<void> {
  return new Promise((resolve) => {
    const ctx = makeContext();
    const dest = ctx.destination;
    const t0 = ctx.currentTime + 0.05;
    const dur = p.durationS;
    const w = p.wave;

    // Reduce per-voice amplitude when multiple voices play simultaneously
    const perVoice = (n: number) => AMPLITUDE / Math.max(1, Math.sqrt(n));

    if (w.kind === "sine") {
      scheduleSine(ctx, dest, w.frequenciesHz[0], t0, dur);
    } else if (w.kind === "harmonic_stack" || w.kind === "interval") {
      const amp = perVoice(w.frequenciesHz.length);
      for (const hz of w.frequenciesHz) {
        scheduleSine(ctx, dest, hz, t0, dur, amp);
      }
    } else if (w.kind === "glissando" || w.kind === "pitch_transform") {
      const startHz = w.frequenciesHz[0];
      const endHz = w.endHz ?? startHz;
      scheduleGlissando(ctx, dest, startHz, endHz, t0, dur);
    } else if (w.kind === "spectral_sweep") {
      // Same as glissando but with a wider range and a touch more amplitude
      const startHz = w.frequenciesHz[0];
      const endHz = w.endHz ?? startHz * 4;
      scheduleGlissando(ctx, dest, startHz, endHz, t0, dur, AMPLITUDE * 0.7);
    } else if (w.kind === "alternation") {
      const toneDur = w.toneDurationS ?? 0.2;
      const gap = w.gapS ?? 0;
      let t = t0;
      let i = 0;
      while (t < t0 + dur) {
        const hz = w.frequenciesHz[i % w.frequenciesHz.length];
        const remaining = t0 + dur - t;
        scheduleSine(ctx, dest, hz, t, Math.min(toneDur, remaining));
        t += toneDur + gap;
        i += 1;
      }
    } else if (w.kind === "sparse_burst") {
      const toneDur = w.toneDurationS ?? 0.1;
      const gap = w.gapS ?? 0.15;
      let t = t0;
      for (const hz of w.frequenciesHz) {
        if (t >= t0 + dur) break;
        scheduleSine(ctx, dest, hz, t, toneDur);
        t += toneDur + gap;
      }
    } else if (w.kind === "pulse_repetition") {
      const hz = w.frequenciesHz[0];
      const count = w.repeatCount ?? 4;
      const period = w.repeatPeriodS ?? 0.3;
      const pulseDur = Math.min(0.15, period * 0.5);
      for (let i = 0; i < count; i++) {
        const t = t0 + i * period;
        scheduleSine(ctx, dest, hz, t, pulseDur);
      }
    }

    const totalWallS = w.kind === "pulse_repetition"
      ? ((w.repeatCount ?? 4) * (w.repeatPeriodS ?? 0.3)) + 0.2
      : dur + 0.2;
    setTimeout(() => {
      void ctx.close().catch(() => undefined);
      resolve();
    }, totalWallS * 1000);
  });
}
