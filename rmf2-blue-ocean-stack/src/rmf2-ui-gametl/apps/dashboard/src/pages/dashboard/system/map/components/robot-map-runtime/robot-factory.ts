import * as THREE from 'three';
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';

import { readNumber, isRecord } from '../utils';
import type { RobotConfig, RobotRuntime } from '../robot-types';

import { tuneMaterials } from './robot-runtime-utils';
import { getInitialRobotPosition } from '../robot-map-coordinates/robot-position';
import {
  coordKey,
  pathKey,
  robotTrailKey,
} from '../robot-map-config/robot-config-keys';
import { createRobotTrail } from '../robot-map-draw-trail/robot-trail';
import { getInitialPathIndex } from '../robot-map-coordinates/waypoint-utils';
import { getInitialModelHeading } from '../robot-map-motion/robot-heading';

export function cloneRobotTemplate(template: THREE.Group) {
  const cloned = cloneSkeleton(template) as THREE.Group;

  cloned.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;

    child.geometry = child.geometry.clone();
    child.material = Array.isArray(child.material)
      ? child.material.map((material) => material.clone())
      : child.material.clone();
  });

  return cloned;
}

export function applyRobotScale(
  root: THREE.Group,
  scale: RobotConfig['scale'],
) {
  if (typeof scale === 'number') {
    root.scale.setScalar(scale);
    return;
  }

  if (isRecord(scale)) {
    root.scale.set(
      readNumber(scale.x, 1),
      readNumber(scale.y, 1),
      readNumber(scale.z, 1),
    );
  }
}

type CreateRobotArgs = {
  config: RobotConfig;
  template: THREE.Group;
  floorZ: number;
  scene: THREE.Scene;
};

export function createRobot({
  config,
  template,
  floorZ,
  scene,
}: CreateRobotArgs): RobotRuntime {
  const visual = cloneRobotTemplate(template);

  // Match the main floor-plan rotation: GLB is usually Y-up, this viewer is Z-up.
  visual.rotation.x = Math.PI / 2;
  tuneMaterials(visual);

  const root = new THREE.Group();
  root.name = `robot:${config.id}`;
  root.add(visual);

  applyRobotScale(root, config.scale);

  const position = getInitialRobotPosition(config, floorZ);
  root.position.set(position.x, position.y, position.z);

  // Initial visual heading only. Live heading should be controlled by movement.
  root.rotation.z = getInitialModelHeading(config.rotationZ);

  scene.add(root);

  const trail = createRobotTrail(config, floorZ, root.position);
  scene.add(trail.group);

  return {
    id: config.id,
    name: config.name ?? config.id,
    root,
    config,
    pathIndex: getInitialPathIndex(config),
    driveState: null,
    status: config.enabled === false ? 'disabled' : 'idle',
    lastConfigPositionKey: coordKey(config.position),
    lastConfigPathKey: pathKey(config.path),
    lastConfigTrailKey: robotTrailKey(config),
    trail,
  };
}
