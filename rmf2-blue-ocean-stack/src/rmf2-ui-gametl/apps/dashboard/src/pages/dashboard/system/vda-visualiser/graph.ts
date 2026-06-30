// Graph helpers for highlighting a robot's remaining route on the map.
// Edges are treated as undirected (the demo map defines both directions).
import type { MapEdge, MapNode } from './types';

export function buildAdjacency(edges: MapEdge[]): Map<string, string[]> {
  const adj = new Map<string, string[]>();
  const link = (a: string, b: string) => {
    const list = adj.get(a) ?? [];
    if (!list.includes(b)) list.push(b);
    adj.set(a, list);
  };
  for (const e of edges) {
    link(e.start_node_id, e.end_node_id);
    link(e.end_node_id, e.start_node_id);
  }
  return adj;
}

// BFS shortest path (inclusive node-id sequence). [] if unreachable.
export function shortestPath(
  adj: Map<string, string[]>,
  start: string,
  goal: string,
): string[] {
  if (start === goal) return [start];
  const prev = new Map<string, string>();
  const visited = new Set<string>([start]);
  const queue: string[] = [start];
  while (queue.length) {
    const cur = queue.shift()!;
    for (const next of adj.get(cur) ?? []) {
      if (visited.has(next)) continue;
      visited.add(next);
      prev.set(next, cur);
      if (next === goal) {
        const path = [goal];
        let n = goal;
        while (prev.has(n)) {
          n = prev.get(n)!;
          path.push(n);
        }
        return path.reverse();
      }
      queue.push(next);
    }
  }
  return [];
}

// Nearest node to a pose — fallback when an AGV has no last_node_id.
export function snapToNode(
  x: number,
  y: number,
  nodes: MapNode[],
): string | null {
  let best: string | null = null;
  let bestDist = Infinity;
  for (const n of nodes) {
    const dist = (n.x - x) ** 2 + (n.y - y) ** 2;
    if (dist < bestDist) {
      bestDist = dist;
      best = n.node_id;
    }
  }
  return best;
}

/** After rack pick/drop the robot departs from the approach node, not the rack. */
export function logicalGraphNode(
  nodeId: string | null | undefined,
  racks: Record<string, string | null>,
): string | null {
  if (!nodeId) return null;
  const approach = racks[nodeId];
  return approach ?? nodeId;
}
