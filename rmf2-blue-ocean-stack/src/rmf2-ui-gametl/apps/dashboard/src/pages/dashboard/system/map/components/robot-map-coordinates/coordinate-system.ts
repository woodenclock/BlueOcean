import {
  type DropPointCoords,
  type RobotCoordinateSystem,
} from '../robot-types';
import { isRecord, readNumber, readCoords } from '../utils';

export function configCoordsToWorld(
  value: unknown,
  fallbackWorld: DropPointCoords,
  coordinateSystem: RobotCoordinateSystem,
): DropPointCoords {
  if (!isRecord(value)) return fallbackWorld;

  if (coordinateSystem === 'world') {
    return readCoords(value, fallbackWorld);
  }

  // navigation-path.json uses the same coordinates as the original GLB path.
  // The viewer rotates GLB content by +90° around X, so convert:
  // source (x, y, z) -> viewer/world (x, -z, y).
  const sourceX = readNumber(value.x, fallbackWorld.x);
  const sourceY = readNumber(value.y, fallbackWorld.z);
  const sourceZ = readNumber(value.z, -fallbackWorld.y);

  return {
    x: sourceX,
    y: -sourceZ,
    z: sourceY,
  };
}
