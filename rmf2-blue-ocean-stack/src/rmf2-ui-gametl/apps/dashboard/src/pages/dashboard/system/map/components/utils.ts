import { type DropPointCoords } from './robot-types';

export function readNumber(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function readCoords(
  value: unknown,
  fallback: DropPointCoords,
): DropPointCoords {
  if (!isRecord(value)) return fallback;

  return {
    x: readNumber(value.x, fallback.x),
    y: readNumber(value.y, fallback.y),
    z: readNumber(value.z, fallback.z),
  };
}
