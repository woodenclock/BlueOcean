// Shared visual constants + the robot colour resolver, used by the SVG canvas,
// the route highlight, and the AGV table so colours stay consistent.
import autoxingImg from '@/assets/autoxing.jpg';
import reemanImg from '@/assets/reeman.jpg';
import { toSchedulerId } from '../scheduler-api';
import type { AgvState, SchedulerRobotId } from '../types';

// Fallback palette for robots we can't map to a known scheduler id.
export const ROBOT_COLORS = ['#3182ce', '#dd6b20', '#38a169', '#d53f8c'];

// Deterministic per-robot colours (independent of AGV array order), keyed by
// robot_id. Unknown robots fall back to the index palette below.
export const ROBOT_COLOR_BY_ID: Record<SchedulerRobotId, string> = {
  'autoxing-1': '#dd6b20',
  'reeman-1': '#3182ce',
  'reeman-2-blue': '#805ad5',
};

export const SELECTED_COLOR = '#38a169'; // green ring on the armed robot
export const GOAL_GOLD = '#d4af37'; // gold ring + "G" marking a goal node

export type PickRackPointOption = {
  id: string;
  label: string;
  /** Layout graph node id (col,row) — display only; spellbook still uses overlay poses. */
  nodeId: string;
  x: number;
  y: number;
  ori: number;
};

// Spellbook overlay id → real-demo layout rack node (maps/gametl_demo_real.layout.yaml).
export const PICK_RACK_NODE_BY_ID: Record<string, string> = {
  Rack_1: '3,4',
  Rack_2: '5,4',
  Rack_3: '6,6',
  Rack_East: '4,6',
  Rack_FarNorth: '4,10',
  Rack_South: '3,4',
  Rack_West: '2,5',
};

/** Layout approach node after spellbook pick/drop at each rack overlay. */
export const PICK_RACK_APPROACH_BY_ID: Record<string, string> = {
  Rack_1: '4,4',
  Rack_2: '4,4',
  Rack_3: '5,6',
  Rack_East: '3,6',
  Rack_FarNorth: '4,9',
  Rack_South: '3,5',
  Rack_West: '3,5',
};

/** Pickup is done when the fork settles into hold (or up). Dropoff when down. */
export function pickRackJackDone(
  mode: 'pickup' | 'dropoff' | 'full',
  jackState: string | null | undefined,
): boolean {
  if (!jackState) return false;
  if (mode === 'pickup') return jackState === 'hold' || jackState === 'up';
  if (mode === 'dropoff') return jackState === 'down';
  return false;
}

export function pickRackNodeId(rackId: string): string {
  return PICK_RACK_NODE_BY_ID[rackId] ?? '—';
}

// Display order for rack location buttons (pickup / drop off columns).
export const PICK_RACK_DISPLAY_ORDER: readonly string[] = [
  'Rack_1',
  'Rack_2',
  'Rack_3',
  'Rack_FarNorth',
  'Rack_East',
  'Rack_West',
  'Rack_South',
];

export function sortPickRackPoints<T extends { id: string }>(
  points: readonly T[],
): T[] {
  const rank = new Map(PICK_RACK_DISPLAY_ORDER.map((id, i) => [id, i]));
  return [...points].sort(
    (a, b) =>
      (rank.get(a.id) ?? Number.MAX_SAFE_INTEGER) -
      (rank.get(b.id) ?? Number.MAX_SAFE_INTEGER),
  );
}

// Spellbook pick_rack overlays (coords match onboard-map frame / CLI pick_rack).
export const PICK_RACK_POINTS_FALLBACK: readonly PickRackPointOption[] = [
  {
    id: 'Rack_1',
    label: '1',
    nodeId: '3,4',
    x: -1.5075,
    y: 4.9925,
    ori: 0.0175,
  },
  {
    id: 'Rack_2',
    label: '2',
    nodeId: '5,4',
    x: 1.9925,
    y: 5.0,
    ori: 3.1416,
  },
  {
    id: 'Rack_3',
    label: '3',
    nodeId: '6,6',
    x: 3.405,
    y: 14.665,
    ori: 3.1416,
  },
  {
    id: 'Rack_FarNorth',
    label: 'FarNorth',
    nodeId: '4,10',
    x: -21.4975,
    y: 6.7775,
    ori: 6.2657,
  },
  {
    id: 'Rack_East',
    label: 'East',
    nodeId: '4,6',
    x: -2.505,
    y: 5.3,
    ori: 4.6949,
  },
  {
    id: 'Rack_West',
    label: 'West',
    nodeId: '2,5',
    x: -0.6075,
    y: 1.6125,
    ori: 1.5533,
  },
  {
    id: 'Rack_South',
    label: 'South',
    nodeId: '3,4',
    x: 1.48,
    y: 3.595,
    ori: 3.1241,
  },
];

// Rack buttons are only shown for AutoXing, and only for the stations the
// VDA5050 master publishes in GET /map (passed in as `live`, already filtered).
// We no longer fall back to PICK_RACK_POINTS_FALLBACK: when the map has no
// stations (e.g. before it loads) we render no rack buttons rather than the full
// hardcoded set. The fallback is kept only as a reference of the overlay poses.
export function pickRackPointsForRobot(
  robotId: string,
  live?: readonly PickRackPointOption[],
): readonly PickRackPointOption[] | null {
  if (!robotId.startsWith('autoxing')) return null;
  if (live && live.length > 0) return sortPickRackPoints(live);
  return [];
}

// Resolve a live AGV's colour: by robot id when known, else by array index.
export function robotColor(agv: AgvState, index: number): string {
  const id = toSchedulerId(agv);
  return (
    (id && ROBOT_COLOR_BY_ID[id]) || ROBOT_COLORS[index % ROBOT_COLORS.length]
  );
}

export function robotImage(agv: AgvState): string | null {
  const id = toSchedulerId(agv);
  if (id?.startsWith('autoxing')) return autoxingImg;
  if (id?.startsWith('reeman')) return reemanImg;
  if (agv.manufacturer === 'Autoxing') return autoxingImg;
  if (agv.manufacturer === 'Reeman') return reemanImg;
  return null;
}

// ---------------------------------------------------------------------------
// Visualiser style zone
// ---------------------------------------------------------------------------
// One place to tune how big everything reads on the map. Bump these to make
// lines thicker, points bigger, and text larger. Per-robot tweaks live in
// ROBOT_VISUAL_BY_ID below, keyed by robot_id (NOT robot type) so individual
// robots can be styled independently.

// White halo behind text so labels stay legible over the map image / edges.
export const TEXT_SHADOW =
  '-1px -1px 2px #fff, 1px -1px 2px #fff, -1px 1px 2px #fff, 1px 1px 2px #fff';

export const VISUAL = {
  edgeWidth: 4, // map graph edges
  nodeRadius: 7, // normal node point
  goalNodeRadius: 10, // node that is a robot's goal
  goalRingWidth: 3, // gold ring on a pending goal
  goalAppliedRingWidth: 5, // gold ring once the goal is dispatched
  nodeLabelSize: 13, // node id text
  coordLabelSize: 11, // node (x, y) text
  goalMarkSize: 16, // the "G" marker beside a goal
};

// Per-robot visual knobs, keyed by robot_id. These cover the bits that are
// drawn once per robot: its remaining-route line, its body marker, and label.
export interface RobotVisualStyle {
  routeWidth: number; // remaining-route line thickness
  routeOpacity: number;
  robotRadius: number; // robot body circle radius
  ringRadius: number; // selection ring radius (armed robot)
  ringWidth: number;
  arrowScale: number; // heading arrow size relative to the default mesh
  labelSize: number; // robot id label font size
}

const ROBOT_VISUAL_DEFAULT: RobotVisualStyle = {
  routeWidth: 8,
  routeOpacity: 0.55,
  robotRadius: 14,
  ringRadius: 20,
  ringWidth: 4,
  arrowScale: 1.4,
  labelSize: 13,
};

// Override any subset per robot_id; anything omitted falls back to the default.
export const ROBOT_VISUAL_BY_ID: Partial<
  Record<SchedulerRobotId, Partial<RobotVisualStyle>>
> = {
  'autoxing-1': {},
  'reeman-1': {},
  'reeman-2-blue': {},
};

// Resolve the full style for a robot_id, merging its overrides over the default.
export function robotStyle(id: SchedulerRobotId | null): RobotVisualStyle {
  const override = id ? ROBOT_VISUAL_BY_ID[id] : undefined;
  return override
    ? { ...ROBOT_VISUAL_DEFAULT, ...override }
    : ROBOT_VISUAL_DEFAULT;
}
