import type { Dispatch, SetStateAction } from 'react';
import { Box, Button, Card, Field, Input, Stack, Text } from '@chakra-ui/react';

import type { DropPointCoords, SceneDebugInfo } from '../robot-types';

type DropPointPanelProps = {
  dropPoint: DropPointCoords;
  setDropPoint: Dispatch<SetStateAction<DropPointCoords>>;
  sceneDebug: SceneDebugInfo | null;
};

function formatCoord(value: number) {
  return value.toFixed(3);
}

export function DropPointPanel({
  dropPoint,
  setDropPoint,
  sceneDebug,
}: DropPointPanelProps) {
  return (
    <Card.Root
      size="sm"
      variant="outline"
      bg="bg/90"
      backdropFilter="blur(4px)"
      pointerEvents="auto"
      w="full"
    >
      <Card.Body gap={3} py={3}>
        <Text fontSize="sm" fontWeight="semibold">
          Drop point
        </Text>

        <Text fontSize="xs" color="fg.muted" lineHeight="short">
          World X, Y on the floor plane; Z is vertical blue axis. Alt+click sets
          X and Y on the plane at the current Z.
        </Text>

        <Stack gap={2}>
          {(['x', 'y', 'z'] as const).map((axis) => (
            <Field.Root key={axis}>
              <Field.Label fontSize="xs" textTransform="uppercase">
                {axis}
              </Field.Label>

              <Input
                size="sm"
                type="number"
                step="0.1"
                fontFamily="mono"
                value={dropPoint[axis]}
                onChange={(event) => {
                  const value = Number.parseFloat(event.target.value);
                  if (Number.isNaN(value)) return;

                  setDropPoint((previous) => ({
                    ...previous,
                    [axis]: value,
                  }));
                }}
              />
            </Field.Root>
          ))}
        </Stack>

        {sceneDebug && (
          <Button
            size="xs"
            variant="outline"
            colorPalette="gray"
            onClick={() =>
              setDropPoint((previous) => ({
                ...previous,
                z: sceneDebug.floorZ,
              }))
            }
          >
            Snap Z to floor ({formatCoord(sceneDebug.floorZ)})
          </Button>
        )}

        <Box
          px={2}
          py={1.5}
          rounded="md"
          bg="bg.subtle"
          borderWidth="1px"
          borderColor="border.subtle"
          fontFamily="mono"
          fontSize="xs"
          color="fg.muted"
          wordBreak="break-all"
        >
          {`"x": ${formatCoord(dropPoint.x)}, "y": ${formatCoord(
            dropPoint.y,
          )}, "z": ${formatCoord(dropPoint.z)}`}
        </Box>
      </Card.Body>
    </Card.Root>
  );
}

export default DropPointPanel;
