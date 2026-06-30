import {
  type RobotConfig,
  type RobotWaypoint,
  type DropPointCoords,
} from '../robot-types';
import { DEFAULT_ROBOT_COLOR } from './robot-map-constants';

export function coordKey(position: Partial<DropPointCoords> | undefined) {
  if (!position) return '';
  return `${position.x ?? ''}:${position.y ?? ''}:${position.z ?? ''}`;
}

export function pathKey(path: RobotWaypoint[] | undefined) {
  if (!path?.length) return '';

  return path
    .map(
      (waypoint) =>
        `${waypoint.id}:${waypoint.label ?? ''}:${waypoint.x}:${waypoint.y}:${waypoint.z}`,
    )
    .join('|');
}

export function robotTrailKey(config: RobotConfig) {
  return [
    config.color ?? DEFAULT_ROBOT_COLOR,
    config.coordinateSystem ?? 'navigation',
    pathKey(config.path),
  ].join('::');
}
