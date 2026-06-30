import * as THREE from 'three';

export function tuneMaterials(root: THREE.Object3D) {
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;

    const materials = Array.isArray(child.material)
      ? child.material
      : [child.material];

    for (const material of materials) {
      // Coplanar faces in architectural exports often z-fight at grazing angles.
      material.polygonOffset = true;
      material.polygonOffsetFactor = 1;
      material.polygonOffsetUnits = 1;

      if (material.transparent || material.opacity < 1) {
        material.depthWrite = false;
        material.side = THREE.FrontSide;
        child.renderOrder = 1;
      } else if (material.side === THREE.DoubleSide) {
        // Back faces fighting with front faces on thin geometry.
        material.side = THREE.FrontSide;
      }
    }
  });
}
