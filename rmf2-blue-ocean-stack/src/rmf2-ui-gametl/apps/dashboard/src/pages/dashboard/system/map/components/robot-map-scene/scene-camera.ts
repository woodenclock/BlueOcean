import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import {
  INTRO_START_DISTANCE_FACTOR,
  END_DISTANCE_FACTOR,
  END_VIEW_ANGLE,
  INTRO_DURATION_MS,
} from '../constants';
import { type CameraFrame } from '../robot-types';

export function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

export function computeCameraFrame(root: THREE.Object3D): CameraFrame {
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const sphere = box.getBoundingSphere(new THREE.Sphere());

  const startDistance = maxDim * INTRO_START_DISTANCE_FACTOR;
  const endDistance = maxDim * END_DISTANCE_FACTOR;

  // Z-up: intro starts straight overhead (high +Z) and ends at an angled view
  // offset along -Y so that +Y projects "up" on screen.
  return {
    center,
    maxDim,
    sphereRadius: sphere.radius,
    startPosition: new THREE.Vector3(
      center.x,
      center.y,
      center.z + startDistance,
    ),
    endPosition: new THREE.Vector3(
      center.x,
      center.y - endDistance * Math.sin(END_VIEW_ANGLE),
      center.z + endDistance * Math.cos(END_VIEW_ANGLE),
    ),
  };
}

export function applyCameraFrame(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  frame: CameraFrame,
  position: THREE.Vector3,
) {
  // Tight near/far improves depth precision and reduces z-fighting.
  camera.near = Math.max(frame.sphereRadius / 500, 0.05);
  camera.far = frame.sphereRadius * 20;
  camera.updateProjectionMatrix();

  controls.target.copy(frame.center);
  controls.minDistance = frame.maxDim * 0.15;
  controls.maxDistance = frame.maxDim * 4;
  camera.position.copy(position);
  camera.lookAt(frame.center);
  controls.update();
}

export function frameCamera(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  root: THREE.Object3D,
) {
  const frame = computeCameraFrame(root);
  applyCameraFrame(camera, controls, frame, frame.endPosition);
}

export function animateIntroCamera(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  frame: CameraFrame,
  isDisposed: () => boolean,
) {
  applyCameraFrame(camera, controls, frame, frame.startPosition);

  const startTime = performance.now();
  const from = frame.startPosition.clone();

  const tick = (now: number) => {
    if (isDisposed()) return;

    const t = Math.min((now - startTime) / INTRO_DURATION_MS, 1);
    const eased = easeInOutCubic(t);

    camera.position.lerpVectors(from, frame.endPosition, eased);
    camera.lookAt(frame.center);
    controls.update();

    if (t < 1) {
      requestAnimationFrame(tick);
    } else {
      applyCameraFrame(camera, controls, frame, frame.endPosition);
    }
  };

  requestAnimationFrame(tick);
}
