import * as THREE from 'three';

export type DropPointPosition = {
  x: number;
  y: number;
  z: number;
};

export class DropPointMarker {
  readonly mesh: THREE.Mesh;

  constructor(radius = 0.1) {
    this.mesh = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 24, 24),
      new THREE.MeshStandardMaterial({
        color: 0xfacc15,
        emissive: 0xca8a04,
        emissiveIntensity: 0.55,
        metalness: 0.15,
        roughness: 0.4,
      }),
    );
    this.mesh.renderOrder = 10;
    this.mesh.visible = false;
  }

  setPosition({ x, y, z }: DropPointPosition) {
    this.mesh.position.set(x, y, z);
  }

  setVisible(visible: boolean) {
    this.mesh.visible = visible;
  }

  pickOnPlane(
    raycaster: THREE.Raycaster,
    planeZ: number,
    target = new THREE.Vector3(),
  ): DropPointPosition | null {
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -planeZ);
    const hit = raycaster.ray.intersectPlane(plane, target);
    if (!hit) return null;
    return { x: hit.x, y: hit.y, z: planeZ };
  }

  dispose() {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.mesh.removeFromParent();
  }
}
