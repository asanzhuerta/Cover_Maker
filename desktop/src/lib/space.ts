/**
 * Disk space checks shown before large downloads: the first-run runtime
 * (the shell's `DiskPlan`) and AI models. The margins match the shell
 * (`runtime.rs`) and the engine (`MODEL_SPACE_MARGIN` in `api/app.py`).
 */

const MIB = 1024 * 1024;
const GIB = 1024 * MIB;

/** Free space kept on top of the runtime estimate. */
export const RUNTIME_MARGIN = 512 * MIB;
/** Free space kept on top of a model's size. */
export const MODEL_MARGIN = 256 * MIB;

export interface DiskPlan {
  torch: string;
  download_bytes: number;
  disk_bytes: number;
  needed_bytes: number;
  free_bytes: number | null;
  folder: string;
}

/** True when the runtime fits, or when the free space is unknown. */
export function runtimeFits(plan: DiskPlan): boolean {
  return (
    plan.free_bytes === null ||
    plan.free_bytes >= plan.needed_bytes + RUNTIME_MARGIN
  );
}

/** Bytes of a model download from the catalogue's size in MB. */
export function modelBytes(sizeMb: number): number {
  return sizeMb * MIB;
}

/** `free_disk_gb` from `GET /system` in bytes. */
export function freeBytesFromGb(freeGb: number): number {
  return Math.round(freeGb * GIB);
}

/** True when a model of `sizeMb` fits in `freeBytes` (unknown free fits). */
export function modelFits(sizeMb: number, freeBytes: number | null): boolean {
  return freeBytes === null || freeBytes >= modelBytes(sizeMb) + MODEL_MARGIN;
}
