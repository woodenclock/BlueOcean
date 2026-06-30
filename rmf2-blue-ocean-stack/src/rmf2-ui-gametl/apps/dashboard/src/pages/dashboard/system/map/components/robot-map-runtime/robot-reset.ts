import type { RobotRuntime } from '../robot-types';

import { ROBOT_MODEL_HEADING_OFFSET } from '../constants';
import { getInitialPathIndex } from '../robot-map-coordinates/waypoint-utils';
import { getInitialRobotPosition } from '../robot-map-coordinates/robot-position';
import { resetRobotTrail } from '../robot-map-draw-trail/robot-trail';

type ResetAllRobotsToStartArgs = {
  robots: Map<string, RobotRuntime>;
  currentFloorZ: number;
  publishRobotStatuses: (force?: boolean) => void;
};

export function resetAllRobotsToStart({
  robots,
  currentFloorZ,
  publishRobotStatuses,
}: ResetAllRobotsToStartArgs) {
  for (const robot of robots.values()) {
    const startPosition = getInitialRobotPosition(robot.config, currentFloorZ);

    robot.root.position.set(startPosition.x, startPosition.y, startPosition.z);

    robot.root.rotation.z =
      (robot.config.rotationZ ?? 0) + ROBOT_MODEL_HEADING_OFFSET;

    robot.pathIndex = getInitialPathIndex(robot.config);
    robot.driveState = null;
    robot.blockedBy = undefined;
    robot.status = robot.config.enabled === false ? 'disabled' : 'idle';

    resetRobotTrail(robot);
  }

  publishRobotStatuses(true);
}
