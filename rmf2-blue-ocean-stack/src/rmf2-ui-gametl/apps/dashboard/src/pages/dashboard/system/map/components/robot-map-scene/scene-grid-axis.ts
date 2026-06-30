import * as THREE from 'three';
import { SceneBounds } from '../robot-types';

export function createGridAxesHelpers(bounds: SceneBounds) {
  const size = bounds.max.clone().sub(bounds.min);
  // Z-up: floor is the XY plane, so the grid extent should span X and Y.
  const gridExtent = Math.max(size.x, size.y) * 1.25;
  const divisions = Math.max(10, Math.round(gridExtent / 2));

  const grid = new THREE.GridHelper(gridExtent, divisions, 0x888888, 0xcccccc);
  // GridHelper is authored in the XZ plane; rotate it into XY for a Z-up scene.
  grid.rotation.x = Math.PI / 2;
  const axes = new THREE.AxesHelper(bounds.maxDim * 0.35);

  const group = new THREE.Group();
  group.add(grid, axes);
  group.position.set(
    (bounds.min.x + bounds.max.x) / 2,
    (bounds.min.y + bounds.max.y) / 2,
    bounds.floorZ,
  );
  group.visible = false;

  return group;
}
