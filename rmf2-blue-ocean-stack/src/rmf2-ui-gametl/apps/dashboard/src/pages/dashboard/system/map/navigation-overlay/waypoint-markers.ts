import * as THREE from 'three';
import type { NavOverlayConfig, PathPoint, WaypointUserData } from './types';
import { createLabelSprite, disposeLabelSprite } from './label-sprite';

export type WaypointMarkerEntry = {
  id: number;
  mesh: THREE.Mesh;
  label: THREE.Sprite | null;
  group: THREE.Group;
  visited: boolean;
};

export function createWaypointMarkers(
  points: PathPoint[],
  worldPoints: THREE.Vector3[],
  config: NavOverlayConfig,
): WaypointMarkerEntry[] {
  const entries: WaypointMarkerEntry[] = [];
  const lastIndex = points.length - 1;

  for (let i = 1; i < lastIndex; i++) {
    const point = points[i];
    const world = worldPoints[i];
    const group = new THREE.Group();
    group.position.set(world.x, world.y, world.z);

    const radius = config.pipeRadius * 1.8;
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 16, 16),
      new THREE.MeshStandardMaterial({
        color: 0x64748b,
        emissive: 0x334155,
        emissiveIntensity: 0.2,
        metalness: 0.25,
        roughness: 0.55,
      }),
    );
    mesh.userData = {
      waypointId: point.id,
      isWaypoint: true,
    } satisfies WaypointUserData;

    group.add(mesh);

    let label: THREE.Sprite | null = null;
    if (point.label) {
      label = createLabelSprite(point.label, config, 0.28);
      label.position.set(0, 0, config.pipeRadius * 4);
      group.add(label);
    }

    entries.push({ id: point.id, mesh, label, group, visited: false });
  }

  return entries;
}

export function setWaypointVisited(
  entry: WaypointMarkerEntry,
  visited: boolean,
  _config: NavOverlayConfig,
) {
  if (entry.visited === visited) return;
  entry.visited = visited;

  const mat = entry.mesh.material as THREE.MeshStandardMaterial;
  if (visited) {
    mat.color.setHex(0xc084fc);
    mat.emissive.setHex(0xa855f7);
    mat.emissiveIntensity = 0.65;
    entry.mesh.scale.setScalar(1.2);
  } else {
    mat.color.setHex(0x64748b);
    mat.emissive.setHex(0x334155);
    mat.emissiveIntensity = 0.2;
    entry.mesh.scale.setScalar(1);
  }
}

export function disposeWaypointMarkers(entries: WaypointMarkerEntry[]) {
  for (const entry of entries) {
    entry.mesh.geometry.dispose();
    (entry.mesh.material as THREE.Material).dispose();
    if (entry.label) disposeLabelSprite(entry.label);
  }
}
