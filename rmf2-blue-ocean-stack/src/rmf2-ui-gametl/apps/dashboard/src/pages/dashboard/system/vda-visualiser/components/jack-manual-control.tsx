// Manual jack up + jack down (master /actions/jack).
import { useState } from 'react';
import { Button, HStack, Stack, Text } from '@chakra-ui/react';

import { postJack } from '../master-api';

interface JackManualControlProps {
  robotId: string;
  size?: 'xs' | 'sm';
  showLabel?: boolean;
  fullWidth?: boolean;
  stopPropagation?: boolean;
}

export function JackManualControl({
  robotId,
  size = 'xs',
  showLabel = true,
  fullWidth = false,
  stopPropagation = false,
}: JackManualControlProps) {
  const [busy, setBusy] = useState<'up' | 'down' | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const sendJack = async (dir: 'up' | 'down') => {
    setBusy(dir);
    setErr(null);
    try {
      await postJack(robotId, dir);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Stack gap={1} width={fullWidth ? 'full' : undefined}>
      {showLabel && (
        <Text fontSize="2xs" textTransform="uppercase" color="gray.500">
          Jack (manual)
        </Text>
      )}
      <HStack gap={1} width={fullWidth ? 'full' : undefined}>
        <Button
          size={size}
          minH={size === 'sm' ? '32px' : undefined}
          py={size === 'sm' ? 1 : undefined}
          colorPalette="blue"
          variant="outline"
          flex="1"
          loading={busy === 'up'}
          disabled={busy !== null}
          onClick={(e) => {
            if (stopPropagation) e.stopPropagation();
            void sendJack('up');
          }}
        >
          Jack up
        </Button>
        <Button
          size={size}
          minH={size === 'sm' ? '32px' : undefined}
          py={size === 'sm' ? 1 : undefined}
          colorPalette="orange"
          variant="outline"
          flex="1"
          loading={busy === 'down'}
          disabled={busy !== null}
          onClick={(e) => {
            if (stopPropagation) e.stopPropagation();
            void sendJack('down');
          }}
        >
          Jack down
        </Button>
      </HStack>
      {err && (
        <Text fontSize="xs" color="red.500" title={err} wordBreak="break-word">
          {err}
        </Text>
      )}
    </Stack>
  );
}

export default JackManualControl;
