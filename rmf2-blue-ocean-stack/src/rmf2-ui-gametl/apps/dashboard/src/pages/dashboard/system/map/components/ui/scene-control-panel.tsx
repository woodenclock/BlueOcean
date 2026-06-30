import { Box, Field, Input, Stack, Switch } from '@chakra-ui/react';

import type { LoadState } from '../robot-types';

type SceneControlPanelProps = {
  loadState: LoadState;

  showGridAxes: boolean;
  onShowGridAxesChange: (checked: boolean) => void;

  showDropPoint: boolean;
  onShowDropPointChange: (checked: boolean) => void;

  showRoofSlice: boolean;
  onShowRoofSliceChange: (checked: boolean) => void;

  roofSliceHeight: number;
  onRoofSliceHeightChange: (height: number) => void;
};

export function SceneControlPanel({
  loadState,
  showGridAxes,
  onShowGridAxesChange,
  showDropPoint,
  onShowDropPointChange,
  showRoofSlice,
  onShowRoofSliceChange,
  roofSliceHeight,
  onRoofSliceHeightChange,
}: SceneControlPanelProps) {
  const isReady = loadState === 'ready';

  return (
    <>
      <Box
        px={2.5}
        py={2}
        rounded="md"
        bg="bg/90"
        borderWidth="1px"
        borderColor="border.subtle"
        backdropFilter="blur(4px)"
        pointerEvents="auto"
      >
        <Stack gap={2}>
          <Switch.Root
            size="sm"
            colorPalette="blue"
            checked={showGridAxes}
            disabled={!isReady}
            onCheckedChange={(details) => onShowGridAxesChange(details.checked)}
          >
            <Switch.HiddenInput />
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
            <Switch.Label fontSize="sm">Grid &amp; axes</Switch.Label>
          </Switch.Root>

          <Switch.Root
            size="sm"
            colorPalette="yellow"
            checked={showDropPoint}
            disabled={!isReady}
            onCheckedChange={(details) =>
              onShowDropPointChange(details.checked)
            }
          >
            <Switch.HiddenInput />
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
            <Switch.Label fontSize="sm">Drop point</Switch.Label>
          </Switch.Root>

          <Switch.Root
            size="sm"
            colorPalette="orange"
            checked={showRoofSlice}
            disabled={!isReady}
            onCheckedChange={(details) =>
              onShowRoofSliceChange(details.checked)
            }
          >
            <Switch.HiddenInput />
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
            <Switch.Label fontSize="sm">Slice roof</Switch.Label>
          </Switch.Root>
        </Stack>
      </Box>

      {showRoofSlice && (
        <Field.Root pointerEvents="auto">
          <Field.Label fontSize="xs">Roof slice Z height</Field.Label>
          <Input
            size="sm"
            type="number"
            step="0.1"
            fontFamily="mono"
            value={roofSliceHeight}
            disabled={!isReady}
            onChange={(event) => {
              const value = Number.parseFloat(event.target.value);
              if (!Number.isNaN(value)) {
                onRoofSliceHeightChange(value);
              }
            }}
          />
        </Field.Root>
      )}
    </>
  );
}

export default SceneControlPanel;
