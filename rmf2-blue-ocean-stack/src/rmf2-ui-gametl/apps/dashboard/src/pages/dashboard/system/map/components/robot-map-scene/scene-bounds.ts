import * as THREE from 'three';
import { SceneDebugInfo, SceneBounds } from '../robot-types';

export function computeSceneBounds(root: THREE.Object3D): SceneBounds {
  const box = new THREE.Box3().setFromObject(root);
  const min = box.min.clone();
  const max = box.max.clone();
  const size = box.getSize(new THREE.Vector3());

  return {
    min,
    max,
    maxDim: Math.max(size.x, size.y, size.z),
    floorZ: min.z,
  };
}

export function toSceneDebugInfo(bounds: SceneBounds): SceneDebugInfo {
  return {
    floorZ: bounds.floorZ,
    min: { x: bounds.min.x, y: bounds.min.y, z: bounds.min.z },
    max: { x: bounds.max.x, y: bounds.max.y, z: bounds.max.z },
  };
}
