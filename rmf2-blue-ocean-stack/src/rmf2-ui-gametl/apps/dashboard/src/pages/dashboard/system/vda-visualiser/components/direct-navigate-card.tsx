// One robot's Direct Control card: master-frame X / Y / optional θ sent
// straight to the robot via /demo/direct-navigate (no map app / no MAPF), plus
// manual jack up / down (master /actions/jack).
import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  Field,
  HStack,
  Input,
  Text,
} from '@chakra-ui/react';

import { postScheduler } from '../scheduler-api';
import { JackManualControl } from './jack-manual-control';

interface DirectNavigateCardProps {
  // Id sent as robot_id — the scheduler accepts planner_id, fleet_id, or serial,
  // so the live AGV id (e.g. "reeman_2") works directly.
  robot: string;
  // Display name (defaults to the id).
  label?: string;
}

export function DirectNavigateCard({ robot, label }: DirectNavigateCardProps) {
  const showJack = !robot.startsWith('reeman');
  const [form, setForm] = useState({ x: '', y: '', theta: '' });
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const send = async () => {
    const x = Number.parseFloat(form.x);
    const y = Number.parseFloat(form.y);
    if (Number.isNaN(x) || Number.isNaN(y)) {
      setStatus('Enter numeric X and Y.');
      return;
    }
    const body: { robot_id: string; x: number; y: number; theta?: number } = {
      robot_id: robot,
      x,
      y,
    };
    if (form.theta.trim() !== '') {
      const theta = Number.parseFloat(form.theta);
      if (!Number.isNaN(theta)) body.theta = theta;
    }
    setBusy(true);
    setStatus('Sending…');
    try {
      await postScheduler('/demo/direct-navigate', { body });
      setStatus(
        `Sent → x=${x}, y=${y}${
          body.theta !== undefined ? `, θ=${body.theta}` : ''
        }.`,
      );
    } catch (err) {
      setStatus(`Failed — ${String(err)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card.Root size="sm" variant="outline" flex="1" minW="260px">
      <Card.Body gap={3} py={3}>
        <Text fontSize="sm" fontWeight="semibold" textTransform="capitalize">
          {label ?? robot}
        </Text>
        <HStack gap={2} align="flex-end">
          {(['x', 'y'] as const).map((axis) => (
            <Field.Root key={axis}>
              <Field.Label fontSize="xs" textTransform="uppercase">
                {axis}
              </Field.Label>
              <Input
                size="sm"
                type="number"
                step="0.1"
                fontFamily="mono"
                value={form[axis]}
                onChange={(event) =>
                  setForm((s) => ({ ...s, [axis]: event.target.value }))
                }
              />
            </Field.Root>
          ))}
          <Field.Root>
            <Field.Label fontSize="xs" textTransform="uppercase">
              θ (opt)
            </Field.Label>
            <Input
              size="sm"
              type="number"
              step="0.1"
              fontFamily="mono"
              placeholder="—"
              value={form.theta}
              onChange={(event) =>
                setForm((s) => ({ ...s, theta: event.target.value }))
              }
            />
          </Field.Root>
        </HStack>
        <Button size="sm" colorPalette="teal" loading={busy} onClick={send}>
          Send
        </Button>
        {status && (
          <Text fontSize="xs" color="gray.600" wordBreak="break-word">
            {status}
          </Text>
        )}

        {showJack && (
          <Box pt={1} borderTopWidth="1px" borderColor="border.subtle">
            <JackManualControl robotId={robot} showLabel />
          </Box>
        )}
      </Card.Body>
    </Card.Root>
  );
}

export default DirectNavigateCard;
