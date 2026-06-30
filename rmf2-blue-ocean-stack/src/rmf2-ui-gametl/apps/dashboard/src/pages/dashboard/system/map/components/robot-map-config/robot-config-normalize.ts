import {
  type RobotConfig,
  type RobotCoordinateSystem,
  type RobotWaypoint,
} from '../robot-types';

import { readNumber, isRecord } from '../utils';

export function normalizeRobotPath(
  value: unknown,
): RobotWaypoint[] | undefined {
  if (!Array.isArray(value)) return undefined;

  return value.filter(isRecord).map((waypoint, index) => ({
    id:
      typeof waypoint.id === 'string' || typeof waypoint.id === 'number'
        ? waypoint.id
        : index,
    label: typeof waypoint.label === 'string' ? waypoint.label : undefined,
    x: readNumber(waypoint.x, 0),
    y: readNumber(waypoint.y, 0),
    z: readNumber(waypoint.z, 0),
  }));
}

export function normalizeCoordinateSystem(
  value: unknown,
): RobotCoordinateSystem {
  return value === 'world' ? 'world' : 'navigation';
}

export function normalizeRobotConfigs(payload: unknown): RobotConfig[] {
  const sharedPath = isRecord(payload)
    ? normalizeRobotPath(payload.path)
    : undefined;
  const sharedCoordinateSystem = isRecord(payload)
    ? normalizeCoordinateSystem(payload.coordinateSystem)
    : 'navigation';

  const rawRobots = Array.isArray(payload)
    ? payload
    : isRecord(payload) && Array.isArray(payload.robots)
      ? payload.robots
      : [];

  return rawRobots.filter(isRecord).map((robot, index) => {
    const robotPath = normalizeRobotPath(robot.path) ?? sharedPath;
    const coordinateSystem = normalizeCoordinateSystem(
      robot.coordinateSystem ?? sharedCoordinateSystem,
    );

    return {
      id:
        typeof robot.id === 'string' && robot.id.trim()
          ? robot.id
          : `robot-${index + 1}`,
      name: typeof robot.name === 'string' ? robot.name : undefined,
      color: typeof robot.color === 'string' ? robot.color : undefined,
      position: isRecord(robot.position) ? robot.position : undefined,
      target:
        isRecord(robot.target) || robot.target === null
          ? robot.target
          : undefined,
      path: robotPath,
      startWaypointIndex: readNumber(robot.startWaypointIndex, 0),
      loop: robot.loop === true,
      speed: readNumber(robot.speed, 1),
      enabled: robot.enabled !== false,
      rotationZ:
        typeof robot.rotationZ === 'number' && Number.isFinite(robot.rotationZ)
          ? robot.rotationZ
          : undefined,
      scale:
        typeof robot.scale === 'number' || isRecord(robot.scale)
          ? robot.scale
          : 1,
      coordinateSystem,
    };
  });
}
