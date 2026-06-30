/**
 * DEMO — client-side differential-drive simulation for the map viewer.
 * Not connected to production RMF / fleet APIs.
 *
 * heading = 0 rad (0°) → forward is +Y; forward = (sin(heading), cos(heading)).
 * +X is heading 90° (π/2 rad).
 */

export const ROBOT_TURN_SPEED_RAD = Math.PI / 2;
export const HEADING_EPSILON = 0.02;
export const POSITION_EPSILON = 0.05;

export type DriveMode = 'drive' | 'turn';

export type XY = { x: number; y: number };

export type DriveState = {
  mode: DriveMode;
  heading: number;
  legFrom: XY;
  legTo: XY;
  /** Final waypoint for the current path leg (may require multiple Manhattan sub-legs). */
  waypointTarget: XY;
  /** Remaining Manhattan corners after the current legTo, before waypointTarget. */
  pendingCorners: XY[];
};

export type DifferentialStepInput = {
  position: XY;
  z: number;
  target: XY;
  state: DriveState | null;
  initialHeading: number;
  speed: number;
  turnSpeed: number;
  arrivalEpsilon: number;
  deltaSeconds: number;
};

export type DifferentialStepResult = {
  position: XY;
  z: number;
  heading: number;
  state: DriveState | null;
  mode: DriveMode | 'idle';
  arrived: boolean;
};

function distance2D(a: XY, b: XY) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return Math.hypot(dx, dy);
}

function headingForLeg(from: XY, to: XY): number | null {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (Math.abs(dx) < POSITION_EPSILON && Math.abs(dy) < POSITION_EPSILON) {
    return null;
  }
  if (Math.abs(dy) < POSITION_EPSILON) {
    return dx > 0 ? Math.PI / 2 : -Math.PI / 2;
  }
  if (Math.abs(dx) < POSITION_EPSILON) {
    return dy > 0 ? 0 : Math.PI;
  }
  return null;
}

/** Expand current→target into axis-aligned sub-legs (Manhattan). */
export function buildManhattanPlan(
  from: XY,
  to: XY,
): { legs: XY[]; corners: XY[] } {
  const dx = to.x - from.x;
  const dy = to.y - from.y;

  if (Math.abs(dx) < POSITION_EPSILON || Math.abs(dy) < POSITION_EPSILON) {
    return { legs: [to], corners: [] };
  }

  const xFirst = Math.abs(dx) >= Math.abs(dy);
  const corner: XY = xFirst ? { x: to.x, y: from.y } : { x: from.x, y: to.y };

  return { legs: [corner, to], corners: [corner] };
}

function normalizeAngle(angle: number) {
  return Math.atan2(Math.sin(angle), Math.cos(angle));
}

function shortestAngleDelta(from: number, to: number) {
  return normalizeAngle(to - from);
}

export function createDriveState(
  position: XY,
  target: XY,
  heading: number,
): DriveState {
  const plan = buildManhattanPlan(position, target);
  const legTo = plan.legs[0];
  const pendingCorners = plan.legs.length > 1 ? plan.legs.slice(1) : [];

  return {
    mode: 'drive',
    heading,
    legFrom: { x: position.x, y: position.y },
    legTo,
    waypointTarget: target,
    pendingCorners,
  };
}

function advanceToNextSubLeg(state: DriveState, position: XY) {
  if (state.pendingCorners.length > 0) {
    const next = state.pendingCorners[0];
    state.pendingCorners = state.pendingCorners.slice(1);
    state.legFrom = { x: position.x, y: position.y };
    state.legTo = next;
    const legHeading = headingForLeg(state.legFrom, state.legTo);
    if (
      legHeading !== null &&
      Math.abs(shortestAngleDelta(state.heading, legHeading)) > HEADING_EPSILON
    ) {
      state.mode = 'turn';
    } else {
      if (legHeading !== null) state.heading = legHeading;
      state.mode = 'drive';
    }
    return;
  }

  state.legFrom = { x: position.x, y: position.y };
  state.legTo = state.waypointTarget;
}

function atLegEnd(position: XY, legTo: XY) {
  return distance2D(position, legTo) <= POSITION_EPSILON;
}

function atWaypoint(position: XY, target: XY, epsilon: number) {
  return distance2D(position, target) <= epsilon;
}

export function stepDifferentialDrive(
  input: DifferentialStepInput,
): DifferentialStepResult {
  const {
    position: posIn,
    z,
    target,
    speed,
    turnSpeed,
    arrivalEpsilon,
    deltaSeconds,
    initialHeading,
  } = input;

  let position = { x: posIn.x, y: posIn.y };
  let state = input.state;

  if (atWaypoint(position, target, arrivalEpsilon)) {
    return {
      position,
      z,
      heading: state?.heading ?? initialHeading,
      state: null,
      mode: 'idle',
      arrived: true,
    };
  }

  if (!state) {
    state = createDriveState(position, target, initialHeading);
    const legHeading = headingForLeg(state.legFrom, state.legTo);
    if (
      legHeading !== null &&
      Math.abs(shortestAngleDelta(state.heading, legHeading)) > HEADING_EPSILON
    ) {
      state.mode = 'turn';
    }
  }

  let heading = state.heading;

  if (state.mode === 'turn') {
    const legHeading = headingForLeg(state.legFrom, state.legTo);
    if (legHeading === null) {
      state.mode = 'drive';
    } else {
      const delta = shortestAngleDelta(heading, legHeading);
      const maxTurn = turnSpeed * deltaSeconds;
      if (Math.abs(delta) <= HEADING_EPSILON) {
        heading = legHeading;
        state.heading = heading;
        state.mode = 'drive';
      } else {
        heading += Math.sign(delta) * Math.min(Math.abs(delta), maxTurn);
        state.heading = heading;
      }
    }

    return {
      position,
      z,
      heading,
      state,
      mode: 'turn',
      arrived: false,
    };
  }

  // drive mode
  const legHeading = headingForLeg(state.legFrom, state.legTo);
  if (legHeading !== null) {
    const alignDelta = shortestAngleDelta(heading, legHeading);
    if (Math.abs(alignDelta) > HEADING_EPSILON) {
      state.mode = 'turn';
      return {
        position,
        z,
        heading,
        state,
        mode: 'turn',
        arrived: false,
      };
    }
    heading = legHeading;
    state.heading = heading;
  }

  const forward = {
    x: Math.sin(heading),
    y: Math.cos(heading),
  };
  const remaining = distance2D(position, state.legTo);
  const step = Math.min(remaining, Math.max(speed, 0) * deltaSeconds);

  position = {
    x: position.x + forward.x * step,
    y: position.y + forward.y * step,
  };

  if (atLegEnd(position, state.legTo)) {
    position = { x: state.legTo.x, y: state.legTo.y };

    if (atWaypoint(position, target, arrivalEpsilon)) {
      return {
        position,
        z,
        heading,
        state: null,
        mode: 'idle',
        arrived: true,
      };
    }

    if (state.pendingCorners.length > 0) {
      advanceToNextSubLeg(state, position);
    } else if (distance2D(position, state.waypointTarget) > POSITION_EPSILON) {
      state.legFrom = position;
      state.legTo = state.waypointTarget;
      const nextHeading = headingForLeg(state.legFrom, state.legTo);
      if (
        nextHeading !== null &&
        Math.abs(shortestAngleDelta(heading, nextHeading)) > HEADING_EPSILON
      ) {
        state.mode = 'turn';
      }
    }
  }

  return {
    position,
    z,
    heading,
    state,
    mode: 'drive',
    arrived: false,
  };
}
