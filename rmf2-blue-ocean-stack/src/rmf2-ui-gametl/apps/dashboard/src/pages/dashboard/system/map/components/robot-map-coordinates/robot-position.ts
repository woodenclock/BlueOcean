import { configCoordsToWorld } from './coordinate-system';
import { type RobotConfig } from '../robot-types';
import { getConfiguredStartWaypointIndex } from './waypoint-utils';

export function getInitialRobotPosition(config: RobotConfig, floorZ: number) {
  const coordinateSystem = config.coordinateSystem ?? 'navigation';
  const defaultWorldPosition = { x: 0, y: 0, z: floorZ };

  if (config.position) {
    return configCoordsToWorld(
      config.position,
      defaultWorldPosition,
      coordinateSystem,
    );
  }

  const startWaypoint = config.path?.[getConfiguredStartWaypointIndex(config)];
  if (startWaypoint) {
    return configCoordsToWorld(
      startWaypoint,
      defaultWorldPosition,
      coordinateSystem,
    );
  }

  return defaultWorldPosition;
}
