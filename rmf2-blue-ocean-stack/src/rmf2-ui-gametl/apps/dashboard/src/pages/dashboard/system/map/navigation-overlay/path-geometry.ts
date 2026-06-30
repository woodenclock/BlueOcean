import * as THREE from 'three';
import type { NavOverlayConfig, PipePieceUserData } from './types';

/** Three.js cylinders are authored along +Y. */
const CYLINDER_AXIS = new THREE.Vector3(0, 1, 0);

/** Same convention as drop point: JSON x,y,z are used verbatim in world space. */
export function pathPointToVector3(point: {
  x: number;
  y: number;
  z: number;
}): THREE.Vector3 {
  return new THREE.Vector3(point.x, point.y, point.z);
}

function orientCylinderBetween(
  mesh: THREE.Mesh,
  start: THREE.Vector3,
  end: THREE.Vector3,
) {
  const direction = end.clone().sub(start);
  const length = direction.length();
  if (length < 1e-6) return;

  const midpoint = start.clone().add(end).multiplyScalar(0.5);
  mesh.position.copy(midpoint);
  mesh.quaternion.setFromUnitVectors(CYLINDER_AXIS, direction.normalize());
  mesh.scale.set(1, length, 1);
}

function createCylinderMesh(
  radius: number,
  material: THREE.MeshStandardMaterial,
): THREE.Mesh {
  const geometry = new THREE.CylinderGeometry(radius, radius, 1, 12);
  return new THREE.Mesh(geometry, material);
}

export type PipeBuildResult = {
  group: THREE.Group;
  materials: {
    pending: THREE.MeshStandardMaterial;
    traversed: THREE.MeshStandardMaterial;
    active: THREE.MeshStandardMaterial;
  };
  segmentDirections: THREE.Vector3[];
  segmentStarts: THREE.Vector3[];
  segmentEnds: THREE.Vector3[];
};

export function buildPathPipe(
  points: THREE.Vector3[],
  config: NavOverlayConfig,
): PipeBuildResult {
  const group = new THREE.Group();
  const pipeRadius = config.pipeRadius;

  const pending = new THREE.MeshStandardMaterial({
    color: 0x6b7280,
    emissive: 0x1f2937,
    transparent: true,
    opacity: 0.35,
    metalness: 0.2,
    roughness: 0.6,
  });
  const traversed = new THREE.MeshStandardMaterial({
    color: 0xa855f7,
    emissive: 0x7c3aed,
    metalness: 0.3,
    roughness: 0.45,
  });
  const active = new THREE.MeshStandardMaterial({
    color: 0xc084fc,
    emissive: 0xa855f7,
    metalness: 0.35,
    roughness: 0.4,
    clippingPlanes: [],
    clipIntersection: false,
  });

  const segmentDirections: THREE.Vector3[] = [];
  const segmentStarts: THREE.Vector3[] = [];
  const segmentEnds: THREE.Vector3[] = [];

  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i];
    const end = points[i + 1];

    segmentStarts.push(start.clone());
    segmentEnds.push(end.clone());

    const dir = end.clone().sub(start);
    const len = dir.length();
    if (len < 1e-6) continue;

    segmentDirections.push(dir.normalize());

    const mesh = createCylinderMesh(pipeRadius, pending);
    orientCylinderBetween(mesh, start, end);
    mesh.userData = {
      segmentIndex: i,
      kind: 'straight',
      isPipe: true,
    } satisfies PipePieceUserData;
    group.add(mesh);
  }

  return {
    group,
    materials: { pending, traversed, active },
    segmentDirections,
    segmentStarts,
    segmentEnds,
  };
}

export function disposePipeGroup(group: THREE.Group) {
  group.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose();
    }
  });
}
