export const SCENE_URL = '/RMF2_SIM/Test_3.glb';
export const ROBOT_MODEL_URL = '/robot.glb';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8008';

export const ROBOTS_CONFIG_URL = `${API_BASE_URL}/api/robots`;

export const ROBOT_CONFIG_REFRESH_MS = 1000;
export const ROBOT_COLLISION_PADDING = 0.05;
export const ROBOT_ARRIVAL_EPSILON = 0.05;

export const ROBOT_MODEL_HEADING_OFFSET = -Math.PI / 2;

export const DRACO_DECODER_PATH =
  'https://www.gstatic.com/draco/versioned/decoders/1.5.6/';

export const INTRO_DURATION_MS = 500;
export const INTRO_START_DISTANCE_FACTOR = 1.5;
export const END_DISTANCE_FACTOR = 0.75;
export const END_VIEW_ANGLE = Math.PI / 4;

export const ROBOT_TRAIL_Z_OFFSET = 0.08;
export const ROBOT_TRAIL_SAMPLE_DISTANCE = 0.25;
export const DEFAULT_ROBOT_COLOR = '#00A3FF';

export const STATIC_COLLISION_IGNORE_NAMES = new Set(['Box128', 'Box127']);
