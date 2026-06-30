# Navigation overlay & map viewer — mistakes to avoid

Notes from building the Three.js path overlay, drop point, and scene viewer. Read this before changing coordinates or path geometry.

---

## 1. Do not remap path JSON coordinates silently

**Mistake:** `pathPointToVector3` treated `z === 0` as “snap to floor” and replaced it with `bounds.floorZ` (`boundingBox.min.z`).

**Why it broke:** Drop point used raw JSON `(x, y, z)`. Path, robot, and waypoints used remapped Z. Users verified vertices with drop point at `z: 0` but the pipe drew at `z: floorZ` — looked “perfect” in drop point and wrong on the path.

**Do instead:**

- Use the same world-space mapping everywhere: `new THREE.Vector3(point.x, point.y, point.z)`.
- If “floor” snapping is needed, make it explicit (UI button, separate field, or a named JSON flag) — not `z === 0`.
- Any debug tool (drop point) and any consumer (pipe, robot, sim) must share one function or one rule.

---

## 2. Align robot / markers with the coordinate convention you document

**Mistake:** Robot center was `z + robotRadius` while drop point sphere center was exactly `(x, y, z)`.

**Why it broke:** Same JSON number meant different physical positions depending on feature.

**Do instead:**

- Pick one meaning per field: e.g. JSON = sphere **center** in world space (what drop point shows).
- Apply the same rule to robot, path vertices, and waypoint markers.

---

## 3. Do not ship broken corner geometry before straight segments work

**Mistake:** Torus corner arcs + trim points were added early. Arc orientation was wrong; straights were shortened and no longer passed through user vertices.

**Why it broke:** Path looked disconnected or offset even when coordinates were correct.

**Do instead:**

- First milestone: straight cylinders **point[i] → point[i+1]** with no trim.
- Add rounded corners only after verts match drop point / JSON on a real GLB.
- Test with sharp turns and with axis-aligned segments (including movement along Z).

---

## 4. Do not assume Three.js default axes = this project’s axes

**Mistake:** Mixed Y-up defaults (e.g. `GridHelper` on XZ) with Z-up floor semantics (`floorZ = min.z`) without stating one convention in code and UI.

**Do instead:**

- Document in types/UI: which axis is up, what path `x/y/z` mean, what heading 0 means.
- Keep drop point hint and path JSON in sync with that doc.

---

## 5. Do not add pulse / extra meshes without a clear spec request

**Mistake:** Implemented pulsing outer shell and nav arrow on the robot; user later asked to remove them.

**Do instead:** Match spec literally for v1; defer “nice to have” motion unless asked.

---

## 6. Toggle off/on should reset state when re-enabled

**Mistake (avoidance):** Navigation toggle was added correctly — disabling hides overlay; enabling calls `reset()` and restarts sim. Keep this pattern for any feature that has animation state.

---

## 7. pnpm store path in this repo

**Note:** Local install may need `--store-dir` matching existing `node_modules` linkage (see CI: `pnpm config set store-dir .pnpm-store`). Not overlay logic, but blocked dependency installs during overlay work.

---

## Quick checklist before merging map/path changes

- [ ] Drop point at `(x,y,z)` === pipe vertex at `(x,y,z)` === robot at start when placed at start JSON.
- [ ] No magic transforms on `0` or empty values unless documented in UI.
- [ ] Path segments connect consecutive JSON points exactly (or document offset).
- [ ] Reload / toggle navigation restarts from path[0] after changes to `navigation-path.json`.

---

## 8. Cylinder geometry origin must match where you position the mesh

**Mistake:** `createCylinderMesh` applied `geometry.translate(0, 0.5, 0)` so the cylinder's *bottom* sat at the local origin, but `orientCylinderBetween` set `mesh.position` to the **midpoint** of A→B. Combined with `scale.y = length`, each segment started at the midpoint of A→B and extended L units along the direction — so the line "spawned" past A and never reached B. Consecutive segments did not visually connect (A–B was offset, B–C was offset, etc.).

**Why it broke:** Two conventions were silently mixed:
- Geometry: bottom-at-origin (expects `position` = segment **start**).
- Positioning: center-at-origin (expects `position` = segment **midpoint**).

**Do instead:**

- Pick one convention per mesh helper and stick with it. For midpoint positioning, leave the cylinder geometry centered (Three.js default spans −0.5..+0.5 along Y) so `position = midpoint`, `scale.y = length` covers exactly start→end.
- If you ever need bottom-at-origin geometry (e.g. for vertical extrusion from a floor), set `position = start` — never midpoint.
- Sanity-check with a two-point path where A and B are far apart: the cylinder ends should land *on* A and B, not beyond them.
