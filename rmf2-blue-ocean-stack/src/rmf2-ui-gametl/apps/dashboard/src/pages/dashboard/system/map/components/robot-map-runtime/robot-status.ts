import type { RobotRuntime, RobotStatus } from '../robot-types';
import { getActiveRobotTarget } from '../robot-map-coordinates/waypoint-utils';

export function toRobotStatus(
  robot: RobotRuntime,
  floorZ: number,
): RobotStatus {
  const activeTarget = getActiveRobotTarget(robot, floorZ);

  return {
    id: robot.id,
    name: robot.name,
    status: robot.config.enabled === false ? 'disabled' : robot.status,
    position: {
      x: robot.root.position.x,
      y: robot.root.position.y,
      z: robot.root.position.z,
    },
    target: activeTarget?.target,
    waypointId: activeTarget?.waypoint?.id,
    waypointLabel: activeTarget?.waypoint?.label,
    waypointIndex: activeTarget?.waypointIndex,
    waypointCount: activeTarget?.waypointCount,
    blockedBy: robot.blockedBy,
  };
}
