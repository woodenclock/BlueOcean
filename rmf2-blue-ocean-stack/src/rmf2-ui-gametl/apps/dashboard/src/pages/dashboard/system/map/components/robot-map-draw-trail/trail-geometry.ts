import * as THREE from 'three';
import { type RobotConfig } from '../robot-types';
import { DEFAULT_ROBOT_COLOR, ROBOT_TRAIL_Z_OFFSET } from '../constants';
import { configCoordsToWorld } from '../robot-map-coordinates/coordinate-system';

export function withTrailOffset(point: THREE.Vector3) {
  return point.clone().add(new THREE.Vector3(0, 0, ROBOT_TRAIL_Z_OFFSET));
}

export function createLineGeometryFromPoints(points: THREE.Vector3[]) {
  const geometry = new THREE.BufferGeometry();

  if (points.length === 0) {
    geometry.setFromPoints([]);
  } else if (points.length === 1) {
    geometry.setFromPoints([points[0], points[0]]);
  } else {
    geometry.setFromPoints(points);
  }

  return geometry;
}

export function getRobotPathWorldPoints(
  config: RobotConfig,
  floorZ: number,
): THREE.Vector3[] {
  const coordinateSystem = config.coordinateSystem ?? 'navigation';

  return (config.path ?? []).map((waypoint) => {
    const world = configCoordsToWorld(
      waypoint,
      { x: 0, y: 0, z: floorZ },
      coordinateSystem,
    );

    return new THREE.Vector3(world.x, world.y, world.z + ROBOT_TRAIL_Z_OFFSET);
  });
}

export function getRobotColor(config: RobotConfig) {
  try {
    return new THREE.Color(config.color ?? DEFAULT_ROBOT_COLOR);
  } catch {
    return new THREE.Color(DEFAULT_ROBOT_COLOR);
  }
}
