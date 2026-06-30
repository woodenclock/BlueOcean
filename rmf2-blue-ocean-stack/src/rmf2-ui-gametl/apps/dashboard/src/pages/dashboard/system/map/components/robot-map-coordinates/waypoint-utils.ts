import {
  type DropPointCoords,
  type RobotWaypoint,
  type RobotRuntime,
  type RobotConfig,
} from '../robot-types';

import { configCoordsToWorld } from './coordinate-system';

import { readNumber } from '../utils';

export function clampWaypointIndex(index: number, waypointCount: number) {
  if (waypointCount <= 0) return 0;
  return Math.min(Math.max(Math.floor(index), 0), waypointCount - 1);
}

export function getConfiguredStartWaypointIndex(config: RobotConfig) {
  const waypointCount = config.path?.length ?? 0;
  return clampWaypointIndex(
    readNumber(config.startWaypointIndex, 0),
    waypointCount,
  );
}

export function getInitialPathIndex(config: RobotConfig) {
  const waypointCount = config.path?.length ?? 0;
  if (waypointCount <= 0) return 0;

  const startWaypointIndex = getConfiguredStartWaypointIndex(config);

  // If a custom position is supplied, treat startWaypointIndex as the first
  // target. If position is omitted, spawn at startWaypointIndex and target the
  // next waypoint.
  if (config.position) return startWaypointIndex;
  if (startWaypointIndex < waypointCount - 1) return startWaypointIndex + 1;
  return config.loop ? 0 : startWaypointIndex;
}

export function getActiveRobotWaypoint(robot: RobotRuntime) {
  const path = robot.config.path;
  if (!path?.length) return undefined;

  const waypointIndex = clampWaypointIndex(robot.pathIndex, path.length);
  return {
    waypoint: path[waypointIndex],
    waypointIndex,
    waypointCount: path.length,
  };
}

export function getActiveRobotTarget(
  robot: RobotRuntime,
  floorZ: number,
):
  | {
      target: DropPointCoords;
      waypoint?: RobotWaypoint;
      waypointIndex?: number;
      waypointCount?: number;
    }
  | undefined {
  const coordinateSystem = robot.config.coordinateSystem ?? 'navigation';
  const fallback = {
    x: robot.root.position.x,
    y: robot.root.position.y,
    z: floorZ,
  };

  const activeWaypoint = getActiveRobotWaypoint(robot);
  if (activeWaypoint) {
    return {
      target: configCoordsToWorld(
        activeWaypoint.waypoint,
        fallback,
        coordinateSystem,
      ),
      ...activeWaypoint,
    };
  }

  if (robot.config.target) {
    return {
      target: configCoordsToWorld(
        robot.config.target,
        fallback,
        coordinateSystem,
      ),
    };
  }

  return undefined;
}
