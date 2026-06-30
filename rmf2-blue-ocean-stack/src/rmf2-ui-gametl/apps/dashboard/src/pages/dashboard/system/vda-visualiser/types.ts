// Shared types for the VDA5050 live visualiser.

export interface MapNode {
  node_id: string;
  x: number;
  y: number;
}

export interface MapEdge {
  edge_id: string;
  start_node_id: string;
  end_node_id: string;
}

export interface MapStation {
  station_id: string;
  station_name: string;
  node_ids: string[];
  x: number;
  y: number;
}

export interface MapData {
  nodes: MapNode[];
  edges: MapEdge[];
  stations: MapStation[];
}

export interface AgvActionState {
  action_id: string;
  action_type: string;
  action_status: string;
  result_description: string;
}

export interface AgvState {
  robot_id: string;
  manufacturer: string;
  serial_number: string;
  connection_status: string | null;
  last_node_id: string | null;
  x: number | null;
  y: number | null;
  theta: number | null;
  has_pose: boolean;
  action_states: AgvActionState[] | null;
  jack_state: string | null;
}

// Master-frame occupancy map image draped behind the topology. `origin` is the
// world pose [x, y] (metres) of the image's lower-left corner; `resolution` is
// metres per pixel; `width`/`height` are the PNG's pixel dimensions.
export interface MapImageMeta {
  url: string;
  resolution: number;
  origin: [number, number];
  width: number;
  height: number;
}

export type SocketStatus = 'connecting' | 'connected' | 'disconnected';

// Robot id accepted by the scheduler's /demo/* endpoints. Now unified with the
// live /state robot_id (e.g. "autoxing-1", "reeman-1", "reeman-2-blue"), so it's
// just a string — no fixed two-robot enum.
export type SchedulerRobotId = string;

// A point-and-click goal for one robot; `applied` once dispatched to MAPF.
export interface RobotGoal {
  node: string;
  applied: boolean;
  /** Set for spellbook pick_rack missions (not MAPF node ids). */
  pickRackMode?: 'pickup' | 'dropoff' | 'full';
}

export type RobotGoals = Record<SchedulerRobotId, RobotGoal>;

// Rack node_id -> approach node id (from GET /demo/racks). Empty if unknown.
export type RackMap = Record<string, string | null>;
