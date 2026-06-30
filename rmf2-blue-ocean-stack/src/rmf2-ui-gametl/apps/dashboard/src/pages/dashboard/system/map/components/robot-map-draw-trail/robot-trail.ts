import * as THREE from 'three';
import {
  type RobotRuntime,
  type RobotTrailRuntime,
  type RobotConfig,
} from '../robot-types';
import { ROBOT_TRAIL_SAMPLE_DISTANCE } from '../constants';
import {
  createLineGeometryFromPoints,
  getRobotColor,
  getRobotPathWorldPoints,
  withTrailOffset,
} from './trail-geometry';

export function createRobotTrail(
  config: RobotConfig,
  floorZ: number,
  startPosition: THREE.Vector3,
): RobotTrailRuntime {
  const color = getRobotColor(config);
  const group = new THREE.Group();
  group.name = `trail:${config.id}`;

  const plannedPoints = getRobotPathWorldPoints(config, floorZ);

  const plannedGeometry = createLineGeometryFromPoints(plannedPoints);
  const activeGeometry = createLineGeometryFromPoints([
    withTrailOffset(startPosition),
    withTrailOffset(startPosition),
  ]);

  const plannedMaterial = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: 0.25,
    depthWrite: false,
    depthTest: false,
  });

  const activeMaterial = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: 1,
    depthWrite: false,
    depthTest: false,
  });

  const plannedLine = new THREE.Line(plannedGeometry, plannedMaterial);
  const activeLine = new THREE.Line(activeGeometry, activeMaterial);

  plannedLine.name = `planned-path:${config.id}`;
  activeLine.name = `active-trail:${config.id}`;

  plannedLine.renderOrder = 20;
  activeLine.renderOrder = 30;

  group.add(plannedLine);
  group.add(activeLine);

  const startPoint = withTrailOffset(startPosition);

  return {
    group,
    plannedLine,
    activeLine,
    plannedMaterial,
    activeMaterial,
    plannedGeometry,
    activeGeometry,
    visitedPoints: [startPoint.clone()],
    lastSampledPoint: startPoint.clone(),
  };
}

export function disposeRobotTrail(trail: RobotTrailRuntime) {
  trail.plannedGeometry.dispose();
  trail.activeGeometry.dispose();
  trail.plannedMaterial.dispose();
  trail.activeMaterial.dispose();
}

export function resetRobotTrail(robot: RobotRuntime) {
  if (!robot.trail) return;

  const startPoint = withTrailOffset(robot.root.position);

  robot.trail.visitedPoints = [startPoint.clone()];
  robot.trail.lastSampledPoint.copy(startPoint);
  robot.trail.activeGeometry.setFromPoints([startPoint, startPoint]);
  robot.trail.activeGeometry.computeBoundingSphere();
}

export function updateRobotTrail(robot: RobotRuntime, force = false) {
  if (!robot.trail) return;

  const currentPoint = withTrailOffset(robot.root.position);
  const distance = currentPoint.distanceTo(robot.trail.lastSampledPoint);

  if (!force && distance < ROBOT_TRAIL_SAMPLE_DISTANCE) return;

  robot.trail.visitedPoints.push(currentPoint.clone());
  robot.trail.lastSampledPoint.copy(currentPoint);

  robot.trail.activeGeometry.setFromPoints(robot.trail.visitedPoints);
  robot.trail.activeGeometry.computeBoundingSphere();
}
