/**
 * Loads the Signalsmith Stretch worklet (MIT) on demand. The module is served
 * from the app's own origin, so the CSP only needs `'wasm-unsafe-eval'` for
 * its WebAssembly and no `blob:` scripts (ADR-012).
 */
import type { StretchNode } from "signalsmith-stretch";
import workletUrl from "signalsmith-stretch-worklet?url";

/** Same tonality limit as the engine export (engine/.../audio/practice.py). */
export const TONALITY_HZ = 8000;

export async function createStretch(
  context: BaseAudioContext,
): Promise<StretchNode> {
  const { default: SignalsmithStretch } = await import("signalsmith-stretch");
  SignalsmithStretch.moduleUrl = workletUrl;
  return SignalsmithStretch(context, {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    outputChannelCount: [2],
  });
}
