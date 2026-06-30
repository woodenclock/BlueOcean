import * as THREE from 'three';
import type { NavOverlayConfig } from './types';

function spinOnZ(mesh: THREE.Object3D, elapsed: number, rpm: number) {
  mesh.rotation.z = elapsed * ((rpm * 2 * Math.PI) / 60);
}

export class GoalMarker {
  readonly group = new THREE.Group();

  private readonly ring: THREE.Mesh;
  private readonly config: NavOverlayConfig;
  private spinEnabled = true;

  constructor(config: NavOverlayConfig) {
    this.config = config;

    const ringRadius = config.robotRadius * 1.8;
    this.ring = new THREE.Mesh(
      new THREE.TorusGeometry(ringRadius, config.pipeRadius * 0.75, 8, 48),
      new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        emissive: 0xd97706,
        emissiveIntensity: 0.7,
        metalness: 0.3,
        roughness: 0.45,
      }),
    );
    // The overlay group is in Y-up space (floor = XZ plane). Rotate the torus
    // from its default XY plane into XZ so it lies flat before the group's
    // Y-up → Z-up rotation is applied.
    this.ring.rotation.x = Math.PI / 2;

    this.group.add(this.ring);
  }

  setPosition(point: THREE.Vector3) {
    this.group.position.set(point.x, point.y, point.z);
    // Drop the ring to the floor (Y=0 in path space) plus a small clearance,
    // cancelling out the group's Y so the ring sits at 0.05 regardless of
    // how high the path point is.
    this.ring.position.set(0, -point.y + 0.05, 0);
  }

  triggerArrival() {
    this.spinEnabled = false;
  }

  reset() {
    this.spinEnabled = true;
  }

  update(elapsed: number) {
    if (this.spinEnabled) {
      spinOnZ(this.ring, elapsed, this.config.goalRingSpinRPM);
    }
  }

  dispose() {
    this.ring.geometry.dispose();
    (this.ring.material as THREE.Material).dispose();
  }
}
