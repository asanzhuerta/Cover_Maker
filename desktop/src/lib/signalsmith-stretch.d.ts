// Types for the Web Audio release of Signalsmith Stretch (MIT), which ships
// without declarations. Remote methods resolve once the worklet answers.
declare module "signalsmith-stretch" {
  export interface StretchSchedule {
    output?: number;
    active?: boolean;
    input?: number;
    rate?: number;
    semitones?: number;
    tonalityHz?: number;
    formantSemitones?: number;
    formantCompensation?: boolean;
    formantBaseHz?: number;
    loopStart?: number;
    loopEnd?: number;
  }

  export interface StretchNode extends AudioWorkletNode {
    inputTime: number;
    schedule(change: StretchSchedule): Promise<void>;
    start(when?: number): Promise<void>;
    stop(when?: number): Promise<void>;
    latency(): Promise<number>;
    configure(options: {
      blockMs?: number | null;
      intervalMs?: number;
      splitComputation?: boolean;
      preset?: "default" | "cheaper";
    }): Promise<void>;
  }

  interface Factory {
    (
      context: BaseAudioContext,
      options?: AudioWorkletNodeOptions,
    ): Promise<StretchNode>;
    /** Same-origin URL of the worklet module (instead of a blob: URL). */
    moduleUrl?: string;
  }

  const SignalsmithStretch: Factory;
  export default SignalsmithStretch;
}
