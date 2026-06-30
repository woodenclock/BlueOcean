// Calls to the VDA5050 master webserver's direct control endpoints.
import { BrokerStatusConfig } from '@/clients';

const MASTER_BASE = (
  BrokerStatusConfig.BASE ?? 'http://localhost:8000'
).replace(/\/$/, '');

export async function postJack(
  robotId: string,
  direction: 'up' | 'down',
): Promise<void> {
  const resp = await fetch(
    `${MASTER_BASE}/actions/jack/${robotId}/${direction}`,
    { method: 'POST' },
  );
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${text.slice(0, 200)}`);
  }
}

// Send VDA5050 instant actions to a robot. Forward-compatible: once adapter-side
// instant-action subscription is wired in C++, this will execute on the robot.
export async function postInstantActions(
  robotId: string,
  actions: Array<{
    action_type: string;
    blocking_type?: string;
    action_description?: string;
  }>,
): Promise<void> {
  const resp = await fetch(`${MASTER_BASE}/actions/instant/${robotId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actions }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${text.slice(0, 200)}`);
  }
}
