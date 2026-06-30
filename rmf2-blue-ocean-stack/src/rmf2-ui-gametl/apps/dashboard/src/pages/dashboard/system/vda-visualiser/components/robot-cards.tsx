// Live per-robot status as cards (connection, pose, jack state). Each card has
// Stop & reset (always clickable — stops robot + clears mission/MAPF state) and
// Navigate (force direct-navigate to the queued map goal, after confirmation).
import { useEffect, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Card,
  HStack,
  Flex,
  Image,
  SimpleGrid,
  Stack,
  Text,
} from '@chakra-ui/react';

import { Tooltip } from '@/components/ui/tooltip';
import type { AgvState, RobotGoal, SchedulerRobotId } from '../types';
import { pickRackPointsForRobot, robotColor, robotImage } from './constants';
import { JackManualControl } from './jack-manual-control';
import type { PickRackPointOption } from './constants';
import type { PickRackMode } from '../scheduler-api';

export interface PickRackSelection {
  mode: PickRackMode;
  pickup: string;
  putdown: string;
  pickupLabel: string;
  putdownLabel: string;
}

const fmt = (v: number | null) => (v == null ? '—' : v.toFixed(2));

function jackBadge(state: string | null) {
  if (state === 'hold') {
    return <Badge colorPalette="green">Hold</Badge>;
  }
  if (state === 'up') {
    return <Badge colorPalette="green">Lifted</Badge>;
  }
  if (state === 'jacking_up') {
    return <Badge colorPalette="yellow">Raising…</Badge>;
  }
  if (state === 'jacking_down') {
    return <Badge colorPalette="yellow">Lowering…</Badge>;
  }
  if (state === 'down') {
    return <Badge colorPalette="gray">Down</Badge>;
  }
  if (state === 'unknown') {
    return <Badge colorPalette="gray">Unknown</Badge>;
  }
  return <Badge colorPalette="gray">—</Badge>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Text fontSize="2xs" textTransform="uppercase" color="gray.500">
        {label}
      </Text>
      <Text fontSize="sm" fontFamily="mono">
        {value}
      </Text>
    </Box>
  );
}

function goalSummary(goal: RobotGoal | undefined) {
  if (!goal) return null;
  if (goal.applied && goal.pickRackMode) {
    return `${goal.node} (pick rack)`;
  }
  return goal.applied ? `${goal.node} (moving)` : goal.node;
}

function forceNavigateTarget(goal: RobotGoal | undefined): string | null {
  if (!goal || goal.pickRackMode) return null;
  return goal.node;
}

// One column of rack buttons (pickup left / drop off right in PickRackRow).
function RackColumn({
  racks,
  value,
  onChange,
  disabled,
  activePalette,
}: {
  racks: readonly PickRackPointOption[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
  activePalette: 'green' | 'orange';
}) {
  return (
    <Stack gap={1} flex="1" minW={0}>
      {racks.map((r) => (
        <Button
          key={r.id}
          size="sm"
          minH="36px"
          h="auto"
          py={1}
          px={2}
          width="full"
          borderRadius="lg"
          variant="outline"
          colorPalette={value === r.id ? activePalette : 'gray'}
          borderWidth={value === r.id ? '2px' : '1px'}
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            onChange(r.id);
          }}
        >
          <Stack gap={0} lineHeight="1.2" align="center" width="full">
            <Text fontSize="sm" fontWeight="semibold">
              {r.label}
            </Text>
            <Text fontSize="2xs" fontFamily="mono" opacity={0.9}>
              {r.nodeId}
            </Text>
          </Stack>
        </Button>
      ))}
    </Stack>
  );
}

// Shared shape for rack action buttons (Pick up / Drop off).
const RACK_ACTION_BTN = {
  size: 'sm' as const,
  minH: '36px',
  py: 1,
  borderRadius: 'lg' as const,
  variant: 'solid' as const,
};

function defaultPickupId(racks: readonly PickRackPointOption[]): string {
  return racks.find((r) => r.id === 'Rack_West')?.id ?? racks[0]?.id ?? '';
}

function defaultPutdownId(
  racks: readonly PickRackPointOption[],
  pickupId: string,
): string {
  return (
    racks.find((r) => r.id === 'Rack_FarNorth' && r.id !== pickupId)?.id ??
    racks.find((r) => r.id !== pickupId)?.id ??
    racks[0]?.id ??
    ''
  );
}

// Spellbook pick_rack row: pill pickup + putdown + actions. Jack badge is live via WS.
function PickRackRow({
  robotId,
  racks,
  pickRackActive,
  onPickRack,
}: {
  robotId: SchedulerRobotId;
  racks: readonly PickRackPointOption[];
  pickRackActive: boolean;
  onPickRack: (
    robotId: SchedulerRobotId,
    selection: PickRackSelection,
  ) => Promise<void>;
}) {
  const [pickup, setPickup] = useState('');
  const [putdown, setPutdown] = useState('');
  const [dispatching, setDispatching] = useState(false);
  const busy = dispatching || pickRackActive;

  useEffect(() => {
    if (racks.length === 0) return;
    setPickup((prev) =>
      prev && racks.some((r) => r.id === prev) ? prev : defaultPickupId(racks),
    );
  }, [racks]);

  useEffect(() => {
    if (racks.length === 0 || !pickup) return;
    setPutdown((prev) =>
      prev && racks.some((r) => r.id === prev)
        ? prev
        : defaultPutdownId(racks, pickup),
    );
  }, [racks, pickup]);

  const labelFor = (id: string) => racks.find((r) => r.id === id)?.label ?? id;

  const run = async (mode: PickRackMode) => {
    setDispatching(true);
    try {
      await onPickRack(robotId, {
        mode,
        pickup,
        putdown,
        pickupLabel: labelFor(pickup),
        putdownLabel: labelFor(putdown),
      });
    } finally {
      setDispatching(false);
    }
  };

  return (
    <Stack
      gap={2}
      borderTopWidth="1px"
      borderColor="border.subtle"
      pt={2}
      onClick={(e) => e.stopPropagation()}
    >
      <Flex
        align="stretch"
        borderWidth="1px"
        borderColor="gray.300"
        borderRadius="lg"
        overflow="hidden"
        bg="bg.subtle"
      >
        <Stack gap={1} flex="1" minW={0} p={1.5}>
          <Text
            fontSize="xs"
            fontWeight="semibold"
            textTransform="uppercase"
            color="green.600"
            letterSpacing="wider"
          >
            Pickup
          </Text>
          <RackColumn
            racks={racks}
            value={pickup}
            activePalette="green"
            onChange={setPickup}
            disabled={busy}
          />
        </Stack>
        <Box
          w="3px"
          flexShrink={0}
          alignSelf="stretch"
          bg="gray.300"
          role="separator"
          aria-orientation="vertical"
        />
        <Stack gap={1} flex="1" minW={0} p={1.5}>
          <Text
            fontSize="xs"
            fontWeight="semibold"
            textTransform="uppercase"
            color="orange.600"
            letterSpacing="wider"
          >
            Drop off
          </Text>
          <RackColumn
            racks={racks}
            value={putdown}
            activePalette="orange"
            onChange={setPutdown}
            disabled={busy}
          />
        </Stack>
      </Flex>
      <HStack gap={2}>
        <Button
          {...RACK_ACTION_BTN}
          colorPalette="green"
          flex="1"
          loading={busy}
          onClick={(e) => {
            e.stopPropagation();
            void run('pickup');
          }}
        >
          Pick up
        </Button>
        <Button
          {...RACK_ACTION_BTN}
          colorPalette="orange"
          flex="1"
          loading={busy}
          onClick={(e) => {
            e.stopPropagation();
            void run('dropoff');
          }}
        >
          Drop off
        </Button>
      </HStack>
    </Stack>
  );
}

function RobotCard({
  agv,
  index,
  selected,
  goal,
  cancelling,
  onSelect,
  onCancel,
  onResetToNode,
  onPickRack,
  pickRackPoints,
}: {
  agv: AgvState;
  index: number;
  selected: boolean;
  goal: RobotGoal | undefined;
  cancelling: boolean;
  onSelect: () => void;
  onCancel: () => void;
  onResetToNode: (robotId: SchedulerRobotId, nodeId: string) => Promise<void>;
  onPickRack: (
    robotId: SchedulerRobotId,
    selection: PickRackSelection,
  ) => Promise<void>;
  pickRackPoints?: readonly PickRackPointOption[];
}) {
  const online = agv.connection_status === 'ONLINE';
  const img = robotImage(agv);
  const mission = goalSummary(goal);

  const [resetting, setResetting] = useState(false);
  const resetTarget = forceNavigateTarget(goal);

  const confirmReset = async () => {
    if (!resetTarget) return;
    setResetting(true);
    try {
      await onResetToNode(agv.robot_id, resetTarget);
    } finally {
      setResetting(false);
    }
  };

  return (
    <Box py={2} px={1} flexShrink={0}>
      <Card.Root
        size="sm"
        variant="outline"
        position="relative"
        zIndex={selected ? 1 : 0}
        outline={selected ? '2px solid' : '2px solid transparent'}
        outlineColor={selected ? 'green.500' : 'transparent'}
        outlineOffset="0px"
        boxShadow={selected ? 'md' : 'none'}
        transform={selected ? 'scale(1.03)' : 'scale(1)'}
        transformOrigin="center"
        transition="transform 0.25s cubic-bezier(0.34, 1.4, 0.64, 1), outline-color 0.2s ease, box-shadow 0.2s ease"
        cursor="pointer"
        onClick={onSelect}
        _hover={{ borderColor: selected ? undefined : 'gray.300' }}
        role="button"
        aria-pressed={selected}
        aria-label={`Select ${agv.robot_id} on map`}
      >
        <Card.Body gap={3} py={3}>
          <HStack justify="space-between" align="flex-start">
            <Stack gap={1}>
              <HStack gap={2}>
                <Box
                  w={3}
                  h={3}
                  borderRadius="full"
                  bg={robotColor(agv, index)}
                />
                <Text fontWeight={700}>{agv.robot_id}</Text>
              </HStack>
              <Badge colorPalette={online ? 'green' : 'gray'} w="fit-content">
                {agv.connection_status ?? 'UNKNOWN'}
              </Badge>
            </Stack>
            {img && (
              <Image
                src={img}
                alt={agv.robot_id}
                h="64px"
                maxW="80px"
                objectFit="contain"
                flexShrink={0}
              />
            )}
          </HStack>

          {mission && (
            <Text fontSize="xs" color="teal.700" fontWeight="medium">
              Goal: {mission}
            </Text>
          )}

          <SimpleGrid columns={3} gap={2}>
            <Stat label="x" value={fmt(agv.x)} />
            <Stat label="y" value={fmt(agv.y)} />
            <Stat label="θ (rad)" value={fmt(agv.theta)} />
          </SimpleGrid>

          <HStack justify="space-between" align="center">
            <HStack gap={2} align="center" flex="1" minW={0}>
              {!agv.robot_id.startsWith('reeman') && (
                <>
                  <Text
                    fontSize="2xs"
                    textTransform="uppercase"
                    color="gray.500"
                  >
                    Jack
                  </Text>
                  {jackBadge(agv.jack_state)}
                </>
              )}
            </HStack>
            <HStack gap={2} flexShrink={0}>
              <Tooltip
                positioning={{ placement: 'top' }}
                openDelay={150}
                closeDelay={50}
                showArrow
                disabled={!resetTarget}
                contentProps={{ maxW: '260px' }}
                content={
                  <Stack gap={1}>
                    <Text fontSize="sm">
                      Directly navigate <b>{agv.robot_id}</b> to goal node{' '}
                      <b>{resetTarget ?? '—'}</b>.
                    </Text>
                    <Text fontSize="xs" opacity={0.8}>
                      Bypasses MAPF and path planning — sends the node
                      coordinates straight to the robot so you can center it
                      manually.
                    </Text>
                  </Stack>
                }
              >
                <Button
                  size="xs"
                  variant="outline"
                  colorPalette="blue"
                  disabled={!resetTarget}
                  loading={resetting}
                  onClick={(e) => {
                    e.stopPropagation();
                    void confirmReset();
                  }}
                >
                  Navigate
                </Button>
              </Tooltip>
              <Button
                size="xs"
                variant="outline"
                colorPalette="red"
                loading={cancelling}
                onClick={(e) => {
                  e.stopPropagation();
                  onCancel();
                }}
              >
                Stop & reset
              </Button>
            </HStack>
          </HStack>

          {agv.robot_id.startsWith('autoxing') && (
            <JackManualControl
              robotId={agv.robot_id}
              size="sm"
              showLabel={false}
              fullWidth
              stopPropagation
            />
          )}

          {(() => {
            const racks = pickRackPointsForRobot(agv.robot_id, pickRackPoints);
            const pickRackActive = Boolean(goal?.applied && goal.pickRackMode);
            return racks && racks.length > 0 ? (
              <PickRackRow
                robotId={agv.robot_id}
                racks={racks}
                pickRackActive={pickRackActive}
                onPickRack={onPickRack}
              />
            ) : null;
          })()}
        </Card.Body>
      </Card.Root>
    </Box>
  );
}

interface RobotCardsProps {
  agvs: AgvState[];
  goals: Partial<Record<SchedulerRobotId, RobotGoal>>;
  selectedRobot: SchedulerRobotId | null;
  cancellingRobot: SchedulerRobotId | null;
  onSelectRobot: (id: SchedulerRobotId) => void;
  onCancelRobot: (id: SchedulerRobotId) => void;
  onResetToNode: (robotId: SchedulerRobotId, nodeId: string) => Promise<void>;
  onPickRack: (
    robotId: SchedulerRobotId,
    selection: PickRackSelection,
  ) => Promise<void>;
  pickRackPoints?: readonly PickRackPointOption[];
}

export function RobotCards({
  agvs,
  goals,
  selectedRobot,
  cancellingRobot,
  onSelectRobot,
  onCancelRobot,
  onResetToNode,
  onPickRack,
  pickRackPoints,
}: RobotCardsProps) {
  if (agvs.length === 0) {
    return (
      <Card.Root size="sm" variant="outline">
        <Card.Body py={4}>
          <Text color="gray.500" fontSize="sm">
            No AGV state received yet.
          </Text>
        </Card.Body>
      </Card.Root>
    );
  }
  return (
    <Stack gap={3}>
      {agvs.map((agv, i) => (
        <RobotCard
          key={agv.robot_id}
          agv={agv}
          index={i}
          selected={selectedRobot === agv.robot_id}
          goal={goals[agv.robot_id]}
          cancelling={cancellingRobot === agv.robot_id}
          onSelect={() => onSelectRobot(agv.robot_id)}
          onCancel={() => onCancelRobot(agv.robot_id)}
          onResetToNode={onResetToNode}
          onPickRack={onPickRack}
          pickRackPoints={pickRackPoints}
        />
      ))}
    </Stack>
  );
}

export default RobotCards;
