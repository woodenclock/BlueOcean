// Point-and-click toolbar: arm robots, queue goals on the map, Apply dispatches
// all pending robots. Clear resets the local queue; Stop & reset halts the
// selected robot and clears mission/MAPF state.
import { Button, HStack, Text, VStack } from '@chakra-ui/react';

import { SCHEDULER_ROBOTS } from '../scheduler-api';
import type { RackMap, RobotGoal, SchedulerRobotId } from '../types';

interface NavControlsProps {
  selectedRobot: SchedulerRobotId | null;
  goals: Partial<Record<SchedulerRobotId, RobotGoal>>;
  racks: RackMap;
  applying: boolean;
  onSelectRobot: (id: SchedulerRobotId) => void;
  onApply: () => void;
  onClear: () => void;
  onStopReset: () => void;
  stopResetLoading: boolean;
}

function goalLabel(goal: RobotGoal | undefined, racks: RackMap) {
  if (!goal) return '—';
  const node = goal.node in racks ? `${goal.node}*` : goal.node;
  return `${node}${goal.applied ? ' (applied)' : ''}`;
}

export function NavControls({
  selectedRobot,
  goals,
  racks,
  applying,
  onSelectRobot,
  onApply,
  onClear,
  onStopReset,
  stopResetLoading,
}: NavControlsProps) {
  const hasPending = (Object.keys(goals) as SchedulerRobotId[]).some(
    (r) => goals[r] != null && !goals[r]!.applied,
  );

  return (
    <VStack align="stretch" gap={3}>
      <HStack flexWrap="wrap" gap={3} align="center">
        <Text fontSize="sm" color="gray.600">
          Arm a robot, click a node to set its goal (rack* = auto pick/drop),
          then Apply:
        </Text>
        {SCHEDULER_ROBOTS.map((r) => (
          <Button
            key={r}
            size="sm"
            variant={selectedRobot === r ? 'solid' : 'outline'}
            colorPalette={selectedRobot === r ? 'green' : 'gray'}
            onClick={() => onSelectRobot(r)}
          >
            {r} · {goalLabel(goals[r], racks)}
          </Button>
        ))}
      </HStack>
      <HStack gap={3} align="center" justify="space-between" w="100%">
        <Button
          size="sm"
          variant="outline"
          colorPalette="red"
          loading={stopResetLoading}
          disabled={selectedRobot == null || applying}
          onClick={onStopReset}
        >
          Stop & reset
        </Button>
        <HStack gap={3}>
          <Button size="sm" variant="outline" onClick={onClear}>
            Clear
          </Button>
          <Button
            size="sm"
            colorPalette="blue"
            loading={applying}
            disabled={!hasPending}
            onClick={onApply}
          >
            Apply
          </Button>
        </HStack>
      </HStack>
    </VStack>
  );
}

export default NavControls;
