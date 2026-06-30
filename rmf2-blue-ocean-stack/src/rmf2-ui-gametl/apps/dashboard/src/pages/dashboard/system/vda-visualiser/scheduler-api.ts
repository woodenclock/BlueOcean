// Calls to the Blue Ocean scheduler's /demo/* endpoints. The generated RTS
// client doesn't cover these routes, so we hit them with plain fetch.
import { SchedulerConfig } from '@/clients';

import type { AgvState, SchedulerRobotId } from './types';

// Fallback robot list shown before any live AGV state arrives. The live list
// (from /state robot_id) is authoritative; this just seeds the demo UI.
export const SCHEDULER_ROBOTS: readonly SchedulerRobotId[] = [
  'autoxing-1',
  'reeman-1',
  // 'reeman-2-blue',
];

const SCHEDULER_BASE = (
  SchedulerConfig.BASE ?? 'http://localhost:8089'
).replace(/\/$/, '');

// The live AGV's robot_id IS the scheduler robot id now (unified) — identity map.
export function toSchedulerId(agv: AgvState): SchedulerRobotId | null {
  return agv.robot_id || null;
}

export class SchedulerConflictError extends Error {
  readonly status = 409;

  constructor(
    readonly detail: string,
    readonly robotId?: SchedulerRobotId,
    readonly pendingGoal?: string,
  ) {
    super(detail);
    this.name = 'SchedulerConflictError';
  }
}

function parseDetail(text: string): string {
  try {
    const body = JSON.parse(text) as { detail?: string };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // fall through
  }
  return text.slice(0, 300);
}

async function schedulerFetch(
  path: string,
  opts?: {
    method?: string;
    body?: unknown;
    query?: Record<string, string>;
    robotId?: SchedulerRobotId;
    pendingGoal?: string;
  },
): Promise<Response> {
  const qs = opts?.query
    ? `?${new URLSearchParams(opts.query).toString()}`
    : '';
  const resp = await fetch(`${SCHEDULER_BASE}${path}${qs}`, {
    method: opts?.method ?? (opts?.body ? 'POST' : 'GET'),
    headers: opts?.body ? { 'Content-Type': 'application/json' } : undefined,
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
  });
  if (resp.status === 409) {
    const text = await resp.text();
    throw new SchedulerConflictError(
      parseDetail(text),
      opts?.robotId,
      opts?.pendingGoal,
    );
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${text.slice(0, 300)}`);
  }
  return resp;
}

export async function postScheduler(
  path: string,
  opts?: { body?: unknown; query?: Record<string, string> },
): Promise<string> {
  const resp = await schedulerFetch(path, opts);
  return resp.text();
}

// `goalJacks` (optional, index-aligned with `goals`) sets an explicit jack
// direction per rack leg for AutoXing — 'up' to pick, 'down' to drop.
export async function navigateMission(
  robotId: SchedulerRobotId,
  goals: string[],
  dryRun = false,
  goalJacks?: (string | null)[],
): Promise<void> {
  await schedulerFetch('/demo/navigate-mission', {
    body: {
      robot_id: robotId,
      goals,
      dry_run: dryRun,
      ...(goalJacks ? { goal_jacks: goalJacks } : {}),
    },
    robotId,
    pendingGoal: goals[goals.length - 1],
  });
}

export interface MissionLegState {
  goal: string;
  is_rack: boolean;
  status: string;
  jack?: string | null;
  detail?: string | null;
}

export interface MissionState {
  robot_id: string;
  dry_run: boolean;
  status: 'running' | 'completed' | 'error' | 'cancelled';
  current_leg: number;
  legs: MissionLegState[];
  detail?: string | null;
}

export async function fetchMissionStatus(
  robotId: SchedulerRobotId,
): Promise<MissionState | null> {
  try {
    const resp = await fetch(
      `${SCHEDULER_BASE}/demo/mission/${encodeURIComponent(robotId)}`,
    );
    if (resp.status === 404) return null;
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`${resp.status} ${text.slice(0, 300)}`);
    }
    return (await resp.json()) as MissionState;
  } catch {
    return null;
  }
}

/** Poll until the mission leaves ``running`` (completed, error, or cancelled). */
export async function pollMissionUntilDone(
  robotId: SchedulerRobotId,
  opts?: { intervalMs?: number; timeoutMs?: number },
): Promise<MissionState> {
  const intervalMs = opts?.intervalMs ?? 1000;
  const timeoutMs = opts?.timeoutMs ?? 600_000;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const state = await fetchMissionStatus(robotId);
    if (!state) {
      throw new Error(`Mission status unavailable for ${robotId}`);
    }
    if (state.status !== 'running') return state;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(`Mission poll timed out for ${robotId}`);
}

export type PickRackMode = 'pickup' | 'dropoff' | 'full';

export interface PickRackPoint {
  id: string;
  label: string | null;
  x: number;
  y: number;
  ori: number;
}

// Rack pick/drop via spellbook pick_rack (no MAPF/VDA5050).
export async function fetchPickRackPoints(
  robotId: SchedulerRobotId = 'autoxing-1',
): Promise<PickRackPoint[]> {
  try {
    const resp = await fetch(
      `${SCHEDULER_BASE}/demo/pick-rack/points?robot_id=${encodeURIComponent(robotId)}`,
    );
    if (!resp.ok) return [];
    const data = (await resp.json()) as { points: PickRackPoint[] };
    return data.points.map((p) => ({
      ...p,
      label: p.label ?? p.id.replace(/^Rack_/, ''),
    }));
  } catch {
    return [];
  }
}

export async function pickRack(
  robotId: SchedulerRobotId,
  mode: PickRackMode,
  pickup?: string,
  putdown?: string,
): Promise<void> {
  await schedulerFetch('/demo/pick-rack', {
    body: {
      robot_id: robotId,
      mode,
      ...(pickup ? { pickup } : {}),
      ...(putdown ? { putdown } : {}),
    },
    robotId,
  });
}

export async function navigateToNode(
  robotId: SchedulerRobotId,
  goalNode: string,
  dryRun = false,
): Promise<void> {
  await schedulerFetch('/demo/navigate-to', {
    body: { robot_id: robotId, goal_node: goalNode, dry_run: dryRun },
    robotId,
    pendingGoal: goalNode,
  });
}

export async function cancelNavigation(
  robotId: SchedulerRobotId,
): Promise<void> {
  await schedulerFetch(
    `/demo/cancel-navigation/${encodeURIComponent(robotId)}`,
    {
      method: 'POST',
      robotId,
    },
  );
}

export interface DemoResetRobotResult {
  robot_id: string;
  mission_cleared: boolean;
  planner_reset_published: boolean;
  robot_stopped: boolean;
}

export interface DemoResetResponse {
  robots: DemoResetRobotResult[];
  master_reset: Record<string, unknown>;
  planner_reset_published: boolean;
}

/** Stop all robots, clear missions, reset MAPF planner (demo recovery). */
export async function demoReset(): Promise<DemoResetResponse> {
  const resp = await schedulerFetch('/demo/demo-reset', { method: 'POST' });
  return (await resp.json()) as DemoResetResponse;
}

// Direct-navigate a robot to a single map node (bypasses MAPF/VDA5050): the
// scheduler resolves the node's master-frame coords and, for Reeman, transforms
// them to robot frame before dispatching to the robot's REST API. Used by the
// robot card Reset button when a map goal is queued.
export async function directNavigateToNode(
  robotId: SchedulerRobotId,
  goalNode: string,
): Promise<void> {
  await schedulerFetch('/demo/direct-navigate', {
    body: { robot_id: robotId, goal_node: goalNode },
    robotId,
  });
}

// Rack nodes (AutoXing pick/drop via rack-direct / explicit goal_jacks): node_id -> approach node.
// Best-effort — returns {} if the scheduler is unreachable so the UI degrades
// gracefully (racks just won't be highlighted / labelled).
export async function fetchRacks(): Promise<Record<string, string | null>> {
  try {
    const resp = await fetch(`${SCHEDULER_BASE}/demo/racks`);
    if (!resp.ok) return {};
    return (await resp.json()) as Record<string, string | null>;
  } catch {
    return {};
  }
}
