import * as THREE from 'three';
import { type StaticCollisionBox, type RobotRuntime } from '../robot-types';
import {
  STATIC_COLLISION_IGNORE_NAMES,
  ROBOT_COLLISION_PADDING,
} from '../constants';

export function collectStaticCollisionBoxes(
  root: THREE.Object3D,
  floorZ: number,
): StaticCollisionBox[] {
  const boxes: StaticCollisionBox[] = [];

  root.updateWorldMatrix(true, true);
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;

    const objectNames = [child.name, child.parent?.name].filter(Boolean);

    if (objectNames.some((name) => STATIC_COLLISION_IGNORE_NAMES.has(name!))) {
      return;
    }

    const box = new THREE.Box3().setFromObject(child);
    const size = box.getSize(new THREE.Vector3());

    if (
      !Number.isFinite(size.x) ||
      !Number.isFinite(size.y) ||
      !Number.isFinite(size.z)
    ) {
      return;
    }

    // Skip flat floor plates, decals, and tiny mesh fragments. Otherwise every
    // robot would constantly collide with the ground it is standing on.
    if (size.x < 0.01 || size.y < 0.01 || size.z < 0.01) return;
    const height = size.z;
    const isVeryFlat = height < 0.25;
    const isNearFloor = box.min.z <= floorZ + 0.2;
    const isLargeFloorLikeSurface =
      isVeryFlat && isNearFloor && size.x > 2 && size.y > 2;

    if (box.max.z <= floorZ + 0.15) return;
    if (isLargeFloorLikeSurface) return;

    boxes.push({
      box: box.expandByScalar(ROBOT_COLLISION_PADDING),
      name: child.name || child.parent?.name || 'scene obstacle',
    });
  });

  return boxes;
}

export function getObjectBox(root: THREE.Object3D) {
  root.updateWorldMatrix(true, true);
  return new THREE.Box3()
    .setFromObject(root)
    .expandByScalar(ROBOT_COLLISION_PADDING);
}

export function findRobotCollision({
  robot,
  robots,
  staticCollisionBoxes,
}: {
  robot: RobotRuntime;
  robots: Map<string, RobotRuntime>;
  staticCollisionBoxes: StaticCollisionBox[];
}) {
  const robotBox = getObjectBox(robot.root);

  for (const obstacle of staticCollisionBoxes) {
    if (robotBox.intersectsBox(obstacle.box)) {
      return obstacle.name;
    }
  }

  for (const otherRobot of robots.values()) {
    if (otherRobot.id === robot.id) continue;
    if (robotBox.intersectsBox(getObjectBox(otherRobot.root))) {
      return otherRobot.name;
    }
  }

  return undefined;
}
