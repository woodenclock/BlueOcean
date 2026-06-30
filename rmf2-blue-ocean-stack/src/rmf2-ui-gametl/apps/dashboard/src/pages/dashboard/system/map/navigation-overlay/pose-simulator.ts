import * as THREE from 'three';
import type { NavOverlayConfig, RobotPose } from './types';

export type PoseSimulatorCallbacks = {
  onWaypointReached?: (waypointId: number, pathIndex: number) => void;
  onArrived?: (goalId: number) => void;
};

export class PoseSimulator {
  private readonly points: THREE.Vector3[];
  private readonly pathIds: number[];
  private readonly config: NavOverlayConfig;
  private readonly callbacks: PoseSimulatorCallbacks;

  private currentSegment = 0;
  private segmentProgress = 0;
  private arrived = false;
  constructor(
    points: THREE.Vector3[],
    pathIds: number[],
    config: NavOverlayConfig,
    callbacks: PoseSimulatorCallbacks = {},
  ) {
    this.points = points;
    this.pathIds = pathIds;
    this.config = config;
    this.callbacks = callbacks;
  }

  get segmentCount() {
    return Math.max(0, this.points.length - 1);
  }

  isArrived() {
    return this.arrived;
  }

  reset() {
    this.currentSegment = 0;
    this.segmentProgress = 0;
    this.arrived = false;
  }

  step(delta: number): RobotPose {
    if (this.arrived || this.points.length < 2) {
      return this.buildPose(0);
    }

    const segIndex = this.currentSegment;
    const start = this.points[segIndex];
    const end = this.points[segIndex + 1];
    const segLen = start.distanceTo(end);
    const travel = this.config.cruiseSpeed * delta;

    if (segLen < 1e-6) {
      this.segmentProgress = 1;
    } else {
      const progressDelta = travel / segLen;
      this.segmentProgress += progressDelta;
    }

    while (this.segmentProgress >= 1 && !this.arrived) {
      this.segmentProgress -= 1;
      const reachedIndex = this.currentSegment + 1;
      if (reachedIndex < this.points.length) {
        this.callbacks.onWaypointReached?.(
          this.pathIds[reachedIndex],
          reachedIndex,
        );
      }

      if (this.currentSegment >= this.segmentCount - 1) {
        this.segmentProgress = 1;
        this.arrived = true;
        this.callbacks.onArrived?.(this.pathIds[this.pathIds.length - 1]);
        break;
      }

      this.currentSegment += 1;
    }

    return this.buildPose(this.arrived ? 0 : this.config.cruiseSpeed);
  }

  private buildPose(speed: number): RobotPose {
    const segIndex = Math.min(
      this.currentSegment,
      Math.max(0, this.segmentCount - 1),
    );
    const start = this.points[segIndex];
    const end = this.points[Math.min(segIndex + 1, this.points.length - 1)];
    const t = THREE.MathUtils.clamp(this.segmentProgress, 0, 1);

    const x = THREE.MathUtils.lerp(start.x, end.x, t);
    const y = THREE.MathUtils.lerp(start.y, end.y, t);
    const z = THREE.MathUtils.lerp(start.z, end.z, t);

    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dz = end.z - start.z;
    let heading = 0;
    if (dx * dx + dy * dy > 1e-8) {
      heading = Math.atan2(dx, dy);
    } else if (dz * dz > 1e-8) {
      // Vertical segment: point fin along horizontal +X (readable fallback).
      heading = dz > 0 ? 0 : Math.PI;
    }

    return {
      x,
      y,
      z,
      heading,
      speed: this.arrived ? 0 : speed,
      currentSegment: segIndex,
      segmentProgress: t,
    };
  }
}
