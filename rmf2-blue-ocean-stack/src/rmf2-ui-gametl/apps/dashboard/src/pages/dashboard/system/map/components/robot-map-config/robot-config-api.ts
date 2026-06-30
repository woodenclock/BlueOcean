import { type RobotConfig } from '../robot-types';
import { ROBOTS_CONFIG_URL } from './robot-map-constants';
import { normalizeRobotConfigs } from './robot-config-normalize';

export async function fetchRobotConfigs(): Promise<RobotConfig[]> {
  const response = await fetch(`${ROBOTS_CONFIG_URL}?t=${Date.now()}`, {
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`Failed to load ${ROBOTS_CONFIG_URL}`);
  }

  return normalizeRobotConfigs(await response.json());
}
