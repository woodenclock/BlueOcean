import type { RobotConfig, RobotSyncContext } from '../robot-types';

import {
  coordKey,
  pathKey,
  robotTrailKey,
} from '../robot-map-config/robot-config-keys';
import { configCoordsToWorld } from '../robot-map-coordinates/coordinate-system';
import { getInitialPathIndex } from '../robot-map-coordinates/waypoint-utils';
import {
  createRobotTrail,
  disposeRobotTrail,
  resetRobotTrail,
} from '../robot-map-draw-trail/robot-trail';
import { applyRobotScale, createRobot } from './robot-factory';
import { disposeObject3D } from '../robot-map-scene/scene-dispose';

type SyncRobotsFromConfigArgs = RobotSyncContext & {
  configs: RobotConfig[];
};

type RemoveRobotArgs = Pick<RobotSyncContext, 'scene' | 'robots'> & {
  id: string;
};

export function removeRobot({ id, scene, robots }: RemoveRobotArgs) {
  const robot = robots.get(id);
  if (!robot) return;

  scene.remove(robot.root);
  disposeObject3D(robot.root);

  if (robot.trail) {
    scene.remove(robot.trail.group);
    disposeRobotTrail(robot.trail);
  }

  robots.delete(id);
}

export function syncRobotsFromConfig({
  configs,
  scene,
  robots,
  template,
  floorZ,
  publishRobotStatuses,
}: SyncRobotsFromConfigArgs) {
  const nextIds = new Set(configs.map((config) => config.id));

  for (const id of Array.from(robots.keys())) {
    if (!nextIds.has(id)) {
      removeRobot({
        id,
        scene,
        robots,
      });
    }
  }

  for (const config of configs) {
    const existing = robots.get(config.id);

    if (!existing) {
      const runtime = createRobot({
        config,
        template,
        floorZ,
        scene,
      });

      robots.set(config.id, runtime);
      continue;
    }

    existing.name = config.name ?? config.id;
    existing.config = config;
    existing.blockedBy = undefined;

    if (config.enabled === false) {
      existing.status = 'disabled';
    }

    const nextPathKey = pathKey(config.path);

    if (nextPathKey !== existing.lastConfigPathKey) {
      existing.pathIndex = getInitialPathIndex(config);
      existing.lastConfigPathKey = nextPathKey;
      existing.driveState = null;
    }

    const nextTrailKey = robotTrailKey(config);

    if (nextTrailKey !== existing.lastConfigTrailKey) {
      if (existing.trail) {
        scene.remove(existing.trail.group);
        disposeRobotTrail(existing.trail);
      }

      existing.trail = createRobotTrail(config, floorZ, existing.root.position);

      scene.add(existing.trail.group);
      existing.lastConfigTrailKey = nextTrailKey;
    }

    const nextPositionKey = coordKey(config.position);

    if (nextPositionKey && nextPositionKey !== existing.lastConfigPositionKey) {
      const position = configCoordsToWorld(
        config.position,
        {
          x: existing.root.position.x,
          y: existing.root.position.y,
          z: floorZ,
        },
        config.coordinateSystem ?? 'navigation',
      );

      existing.root.position.set(position.x, position.y, position.z);
      existing.pathIndex = getInitialPathIndex(config);
      existing.lastConfigPositionKey = nextPositionKey;
      existing.driveState = null;

      resetRobotTrail(existing);
    }

    applyRobotScale(existing.root, config.scale);
  }

  publishRobotStatuses(true);
}
