import * as THREE from 'three';
import { DropPointCoords } from '../robot-types';

export function stepDirectlyTowardWaypoint({
  current,
  target,
  speed,
  deltaSeconds,
  arrivalEpsilon,
  previousHeading,
}: {
  current: THREE.Vector3;
  target: DropPointCoords;
  speed: number;
  deltaSeconds: number;
  arrivalEpsilon: number;
  previousHeading: number;
}) {
  const targetPosition = new THREE.Vector3(target.x, target.y, target.z);
  const toTarget = targetPosition.clone().sub(current);
  const distance = toTarget.length();

  const dx = target.x - current.x;
  const dy = target.y - current.y;
  const heading =
    Math.abs(dx) > 0.000001 || Math.abs(dy) > 0.000001
      ? Math.atan2(dy, dx)
      : previousHeading;

  if (distance <= arrivalEpsilon) {
    return {
      position: targetPosition,
      heading,
      arrived: true,
    };
  }

  if (speed <= 0 || deltaSeconds <= 0) {
    return {
      position: current.clone(),
      heading: previousHeading,
      arrived: false,
    };
  }

  const travelDistance = Math.min(speed * deltaSeconds, distance);
  const direction = toTarget.normalize();
  const nextPosition = current
    .clone()
    .add(direction.multiplyScalar(travelDistance));

  return {
    position: nextPosition,
    heading,
    arrived: nextPosition.distanceTo(targetPosition) <= arrivalEpsilon,
  };
}
