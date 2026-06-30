import type * as THREE from 'three';

/** Yaw about +Z in the XY plane; 0 rad = +Y forward (+Y in XY). */
export const HEADING_ZERO_RAD = 0;

export type PathPoint = {
  id: number;
  x: number;
  y: number;
  z: number;
  label?: string;
};

export type PathDefinition = {
  path: PathPoint[];
};

export type RobotPose = {
  x: number;
  y: number;
  z: number;
  heading: number;
  speed: number;
  currentSegment: number;
  segmentProgress: number;
};

export type NavOverlayConfig = {
  pipeRadius: number;
  cornerRadius: number;
  robotRadius: number;
  markerHeightOffset: number;
  goalRingSpinRPM: number;
  labelMinScreenSize: number;
  labelMaxScreenSize: number;
  cruiseSpeed: number;
};

export type SceneBounds = {
  min: THREE.Vector3;
  max: THREE.Vector3;
  maxDim: number;
  floorZ: number;
};

export type PipePieceKind = 'straight' | 'corner';

export type PipePieceUserData = {
  segmentIndex: number;
  kind: PipePieceKind;
  isPipe: true;
};

export type WaypointUserData = {
  waypointId: number;
  isWaypoint: true;
};

export type NavOverlayEvents = {
  'robot:arrived': { goalId: number };
  'robot:waypointReached': { waypointId: number };
  'waypoint:selected': { waypointId: number };
  'path:reset': Record<string, never>;
};

export type RobotColorState = 'moving' | 'idle' | 'arrived';
