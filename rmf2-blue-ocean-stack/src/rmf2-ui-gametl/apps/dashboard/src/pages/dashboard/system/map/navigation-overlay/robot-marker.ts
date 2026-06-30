import * as THREE from 'three';
import type { NavOverlayConfig, RobotColorState } from './types';

const COLOR_MOVING = { color: 0xe879f9, emissive: 0xdb2777 };
const COLOR_IDLE = { color: 0x60a5fa, emissive: 0x2563eb };
const COLOR_ARRIVED = { color: 0x4ade80, emissive: 0x16a34a };

export class RobotMarker {
  readonly group = new THREE.Group();

  private readonly core: THREE.Mesh;
  private colorState: RobotColorState = 'moving';

  constructor(config: NavOverlayConfig) {
    const r = config.robotRadius;

    this.core = new THREE.Mesh(
      new THREE.SphereGeometry(r, 24, 24),
      new THREE.MeshStandardMaterial({
        color: COLOR_MOVING.color,
        emissive: COLOR_MOVING.emissive,
        emissiveIntensity: 0.85,
        metalness: 0.2,
        roughness: 0.35,
      }),
    );

    this.group.add(this.core);
  }

  setPosition(x: number, y: number, z: number) {
    // Match drop point: JSON coordinates are the sphere center in world space.
    this.group.position.set(x, y, z);
  }

  setHeading(heading: number) {
    this.group.rotation.z = heading;
  }

  setColorState(state: RobotColorState) {
    if (state === this.colorState) return;
    this.colorState = state;
    const palette =
      state === 'arrived'
        ? COLOR_ARRIVED
        : state === 'idle'
          ? COLOR_IDLE
          : COLOR_MOVING;
    const coreMat = this.core.material as THREE.MeshStandardMaterial;
    coreMat.color.setHex(palette.color);
    coreMat.emissive.setHex(palette.emissive);
  }

  dispose() {
    this.core.geometry.dispose();
    (this.core.material as THREE.Material).dispose();
  }
}
