# AutoXing — rack pickup setup for the demo

> ARES PRIVATE — internal demo data (robot IPs, map ids, calibration values are
> sensitive; do not paste live credentials or addresses into this file).

This page documents how the **AutoXing** robot picks up and drops off a rack
during the Blue Ocean demo. For the quick demo we do **not** model the rack in
RMF or the MAPF planner — we use the **rack feature built into the robot's
tablet** (the AutoXing mapping/operations app). The robot handles the final
approach, docking, lift, and reverse-out itself; our stack only dispatches the
robot to the node next to the rack via VDA5050.

Audience: whoever sets up the physical floor before a run. The stack-side
topology and coordinates live in [`real-demo-node-coords.md`](./real-demo-node-coords.md);
this page is the on-robot half.

---

## How the rack feature fits the demo

```
RMF / scheduler ──VDA5050 order──▶ autoxing-adapter-real ──REST──▶ AutoXing robot
   (our stack)                          (AUTOXING_BASE_URL)            │
                                                                       ▼
                                                          tablet "rack" action:
                                                          approach → dock → lift
                                                          → reverse out along path
```

- Our stack drives the robot **to the node beside the rack** (a normal VDA5050
  node from `maps/<VDA5050_MAP_ID>/real.layout.lif.json`, served by the master in the
  AutoXing "l1-artc" frame).
- The **rack pickup/drop itself is owned by the robot**. It is configured once,
  on the tablet, against the same onboard map the adapter selects at startup
  (`maps/autoxing-1_map/`, AutoXing map id **27** — see `maps/<VDA5050_MAP_ID>/robots.yaml`).
- Because the rack is tablet-side, **the rack will not appear in the planner
  grid or the VDA5050 visualiser.** That is expected for the quick demo.

> The rack is defined in **map coordinates**. If you re-map or switch the
> onboard map, the rack label and its calibration must be redone — they are
> tied to that specific map.

---

## Prerequisites

- [ ] Robot is **localized** on the demo onboard map (`maps/autoxing-1_map/`,
      id 27). Verify the live pose on the tablet matches the floor before
      labelling anything.
- [ ] The physical rack is in its final position and **will not move** between
      calibration and the run. The calibration is a fixed map pose; moving the
      rack invalidates it.
- [ ] You can reach the tablet's mapping/operations application (the same app
      used to build "l1-artc").
- [ ] Tablet firmware exposes the rack / jack-up ("顶升" / lift) feature. If the
      rack action is missing from the action list, the feature is not enabled
      on this firmware — stop and resolve that first.

---

## Setup procedure (tablet)

All four steps are done **directly in the mapping application**, on the onboard
map, with the robot localized.

### 1. Label the rack location

Open the map in the tablet app and add a **rack marker** at the rack's real
position. This records the rack's pose (x, y, θ) in the map frame. Place the
marker as accurately as you can — the calibration in step 2 refines it, but a
bad initial label makes calibration fail or drift.

### 2. Calibrate against the physical rack

With the rack physically in place, run the app's **rack calibration** routine.
The robot drives up to the rack and uses its sensors (laser profile of the rack
legs) to lock the exact rack pose and docking offset. This is what lets the
robot dock repeatably.

- Re-run calibration if the rack is ever moved, or if docking starts missing.
- Keep the area around the rack clear during calibration — stray legs/obstacles
  corrupt the leg profile.

### 3. Draw a path to/from the rack  ← **required**

Draw a path in the map connecting the corridor/approach node to the rack.

- **Direction:** the path may be **directional or bi-directional**. For this
  demo, **bi-directional is correct and sufficient** — set it bi-directional.
- **Why it matters:** the robot **reverses into / out of the rack** along this
  path. **If no path is drawn, the robot cannot reverse into the rack** and the
  pickup will fail. This is the single most common setup miss — do not skip it.

```
   approach node ●━━━━━━━━━━━━━━●  rack  (bi-directional path)
                 ◀──── reverse-in / reverse-out ────▶
```

### 4. Save and verify

Save the map from the tablet so the rack marker, calibration, and path persist
on the robot. Then dry-run the rack action once **from the tablet** (not yet via
our stack) and confirm:

- robot approaches the labelled rack,
- docks/lifts cleanly,
- reverses out along the drawn path.

Only once the tablet-side action works end to end should you drive it from the
stack.

---

## Driving it from the stack

Once the rack is set up on the tablet, the run is normal:

1. Ensure the robot is localized on its onboard map — see
   [`real-demo-node-coords.md`](./real-demo-node-coords.md).
2. Bring up the real-demo adapters with the AutoXing robot reachable:
   ```bash
   docker compose --profile real-demo up -d mqtt-broker vda5050-real autoxing-1-real reeman-1-real
   ```
   The `autoxing-1` `endpoint` in `maps/<VDA5050_MAP_ID>/robots.yaml` (e.g. `http://<robot-ip>:8090`)
   must point at the robot's REST endpoint; the adapter reads it from the master
   `/robots` at startup and switches the robot to onboard map id 27.
3. The scheduler dispatches the robot to the **node beside the rack**; the
   tablet rack action does the dock/lift/reverse from there.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Robot reaches the node but won't enter the rack | **No path drawn** to the rack (step 3) | Draw a bi-directional path from the approach node to the rack; save. |
| Docks crooked / misses the rack | Stale or bad calibration; rack was moved | Re-run rack calibration (step 2) at the current rack position. |
| Rack action not in the tablet action list | Rack/lift feature not enabled on firmware | Enable the rack feature; not solvable from our stack. |
| Rack pose wrong after re-mapping | Rack is tied to the old map | Re-label + re-calibrate + re-draw path on the new onboard map. |
| Robot localized wrong before setup | Pose not matched to map | Re-localize on `maps/autoxing-1_map/` (id 27) before labelling. |

---

## Notes / limitations (quick demo)

- The rack is **invisible to RMF, the scheduler, the MAPF planner, and the
  VDA5050 visualiser** — it lives only on the robot. This is intentional for the
  quick demo and is not a production rack-handling integration.
- Calibration and path are **per-map and per-rack-position**. Treat them as
  fragile: re-map, moved rack, or swapped onboard map ⇒ redo steps 1–4.
- Reeman has no rack role in this demo; this page is AutoXing-only.
