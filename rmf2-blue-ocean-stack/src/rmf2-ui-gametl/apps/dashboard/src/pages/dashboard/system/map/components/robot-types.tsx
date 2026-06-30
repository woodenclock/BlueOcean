import * as THREE from 'three';
import { type DriveState } from '../differential-drive.demo';

export type LoadState = 'loading' | 'ready' | 'error';

export type CameraFrame = {
  center: THREE.Vector3;
  maxDim: number;
  sphereRadius: number;
  startPosition: THREE.Vector3;
  endPosition: THREE.Vector3;
};

export type SceneBounds = {
  min: THREE.Vector3;
  max: THREE.Vector3;
  maxDim: number;
  floorZ: number;
};

export type SceneDebugInfo = {
  floorZ: number;
  min: { x: number; y: number; z: number };
  max: { x: number; y: number; z: number };
};

export type DropPointCoords = { x: number; y: number; z: number };
export type RobotMotionStatus =
  | 'idle'
  | 'moving'
  | 'blocked'
  | 'disabled'
  | 'arrived';
export type RobotCoordinateSystem = 'navigation' | 'world';

export type RobotWaypoint = DropPointCoords & {
  id: string | number;
  label?: string;
};

export type RobotConfig = {
  id: string;
  name?: string;
  position?: Partial<DropPointCoords>;
  target?: Partial<DropPointCoords> | null;
  path?: RobotWaypoint[];
  startWaypointIndex?: number;
  loop?: boolean;
  speed?: number;
  enabled?: boolean;
  rotationZ?: number;
  scale?: number | Partial<DropPointCoords>;
  coordinateSystem?: RobotCoordinateSystem;
  color?: string;
};

export type RobotStatus = {
  id: string;
  name: string;
  status: RobotMotionStatus;
  position: DropPointCoords;
  target?: DropPointCoords;
  waypointId?: string | number;
  waypointLabel?: string;
  waypointIndex?: number;
  waypointCount?: number;
  blockedBy?: string;
};

export type RobotTrailRuntime = {
  group: THREE.Group;
  plannedLine: THREE.Line;
  activeLine: THREE.Line;
  plannedMaterial: THREE.LineBasicMaterial;
  activeMaterial: THREE.LineBasicMaterial;
  plannedGeometry: THREE.BufferGeometry;
  activeGeometry: THREE.BufferGeometry;
  visitedPoints: THREE.Vector3[];
  lastSampledPoint: THREE.Vector3;
};

export type RobotRuntime = {
  id: string;
  name: string;
  root: THREE.Group;
  config: RobotConfig;
  pathIndex: number;
  lastConfigPositionKey: string;
  lastConfigPathKey: string;
  driveState: DriveState | null;
  blockedBy?: string;
  status: RobotMotionStatus;
  lastConfigTrailKey: string;
  trail?: RobotTrailRuntime;
};

export type StaticCollisionBox = {
  box: THREE.Box3;
  name: string;
};

export type SceneViewerApi = {
  setShowGridAxes: (show: boolean) => void;
  setDropPointEnabled: (enabled: boolean) => void;
  setDropPointPosition: (position: DropPointCoords) => void;
  setRoofSliceEnabled: (enabled: boolean) => void;
  setRoofSliceHeight: (height: number) => void;
};

export type RobotSyncContext = {
  scene: THREE.Scene;
  robots: Map<string, RobotRuntime>;
  template: THREE.Group;
  floorZ: number;
  publishRobotStatuses: (force?: boolean) => void;
};
