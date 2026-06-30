import * as THREE from 'three';
import type { NavOverlayConfig } from './types';

function makeLabelCanvas(text: string, fontSize = 48) {
  const border = 4;
  const ctx = document.createElement('canvas').getContext('2d');
  if (!ctx) throw new Error('Canvas 2D not available');

  const font = `bold ${fontSize}px sans-serif`;
  ctx.font = font;
  const metrics = ctx.measureText(text);
  const width = Math.ceil(metrics.width) + border * 2;
  const height = fontSize + border * 2;
  ctx.canvas.width = width;
  ctx.canvas.height = height;
  ctx.font = font;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#f8fafc';
  ctx.fillText(text, width / 2, height / 2);
  return ctx.canvas;
}

export function createLabelSprite(
  text: string,
  config: NavOverlayConfig,
  worldScale = 0.35,
): THREE.Sprite {
  const canvas = makeLabelCanvas(text);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(material);
  const aspect = canvas.width / canvas.height;
  // Authored ("base") scale — never mutated. Per-frame scale is derived from this.
  const baseY = worldScale;
  const baseX = worldScale * aspect;
  sprite.scale.set(baseX, baseY, 1);

  sprite.onBeforeRender = (renderer, _scene, camera) => {
    const distance = sprite.position.distanceTo(camera.position);
    const fov = (camera as THREE.PerspectiveCamera).fov ?? 45;
    const vHeight = 2 * Math.tan(THREE.MathUtils.degToRad(fov) / 2) * distance;
    const pxPerWorld = renderer.domElement.clientHeight / vHeight;
    const baseScreenPx = baseY * pxPerWorld;

    if (baseScreenPx < config.labelMinScreenSize) {
      sprite.visible = false;
      return;
    }
    sprite.visible = true;
    if (baseScreenPx > config.labelMaxScreenSize) {
      const clampY = config.labelMaxScreenSize / pxPerWorld;
      sprite.scale.y = clampY;
      sprite.scale.x = clampY * aspect;
    } else if (sprite.scale.y !== baseY) {
      sprite.scale.y = baseY;
      sprite.scale.x = baseX;
    }
  };

  return sprite;
}

export function disposeLabelSprite(sprite: THREE.Sprite) {
  const material = sprite.material as THREE.SpriteMaterial;
  material.map?.dispose();
  material.dispose();
}
