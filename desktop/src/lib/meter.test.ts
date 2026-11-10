import { describe, expect, it } from "vitest";
import {
  MAX_POINTS,
  METER_FLOOR_DB,
  PEAK_HOLD_S,
  RELEASE_DB_PER_S,
  downsample,
  envelopePeak,
  envelopePoints,
  meterShare,
  meterStep,
  silentMeter,
  toDb,
} from "./meter";

describe("meter ballistics", () => {
  it("rises at once and falls at the IEC type I rate", () => {
    const up = meterStep(silentMeter(), -6, 0.033);
    expect(up.db).toBe(-6);
    expect(up.peak).toBe(-6);
    const down = meterStep(up, METER_FLOOR_DB, 0.5);
    expect(down.db).toBeCloseTo(-6 - RELEASE_DB_PER_S * 0.5);
    // 20 dB in 1.7 s.
    expect(meterStep(up, METER_FLOOR_DB, 1.7).db).toBeCloseTo(-26);
  });

  it("holds the peak marker, then lets it fall", () => {
    let meter = meterStep(silentMeter(), -3, 0.03);
    meter = meterStep(meter, METER_FLOOR_DB, PEAK_HOLD_S - 0.1);
    expect(meter.peak).toBe(-3);
    meter = meterStep(meter, METER_FLOOR_DB, 0.2);
    expect(meter.peak).toBeLessThan(-3);
    expect(meter.peak).toBeGreaterThanOrEqual(meter.db);
  });

  it("never goes below the floor", () => {
    const meter = meterStep(silentMeter(), -200, 10);
    expect(meter.db).toBe(METER_FLOOR_DB);
    expect(toDb(0)).toBe(METER_FLOOR_DB);
    expect(toDb(1)).toBe(0);
  });

  it("maps dBFS to the scale", () => {
    expect(meterShare(0)).toBe(1);
    expect(meterShare(METER_FLOOR_DB)).toBe(0);
    expect(meterShare(METER_FLOOR_DB / 2)).toBeCloseTo(0.5);
    expect(meterShare(3)).toBe(1);
  });
});

describe("meter envelopes", () => {
  const envelope = [
    [-0.1, 0.1],
    [-0.8, 0.2],
    [-0.3, 0.5],
    [0, 0],
  ];

  it("asks for 25 points per second within the engine limits", () => {
    expect(envelopePoints(60)).toBe(1500);
    expect(envelopePoints(1)).toBe(50);
    expect(envelopePoints(3600)).toBe(MAX_POINTS);
  });

  it("keeps short peaks between two updates", () => {
    // Four points over 0.4 s: 0.1 s each.
    expect(envelopePeak(envelope, 0.4, 0, 0.25)).toBe(0.8);
    expect(envelopePeak(envelope, 0.4, 0.21, 0.22)).toBe(0.5);
    expect(envelopePeak([], 4, 0, 1)).toBe(0);
  });

  it("reads only the current point after a jump", () => {
    const long = Array.from({ length: 100 }, (_, i) =>
      i === 10 ? [-1, 1] : [0, 0.1],
    );
    expect(envelopePeak(long, 100, 0, 90)).toBe(0.1);
    expect(envelopePeak(long, 100, 50, 10.2)).toBe(1);
  });

  it("downsamples to min and max per bucket", () => {
    expect(downsample(envelope, 2)).toEqual([
      [-0.8, 0.2],
      [-0.3, 0.5],
    ]);
    expect(downsample(envelope, 10)).toBe(envelope);
  });
});
