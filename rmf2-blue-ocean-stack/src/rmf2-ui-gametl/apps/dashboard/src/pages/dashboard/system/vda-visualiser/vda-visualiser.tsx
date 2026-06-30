// VDA5050 live visualiser page. Streams the master map + AGV poses, lets you
// drive robots two ways: point-and-click by node (full MAPF) and direct
// master-frame X/Y (bypass). Composition only — logic lives in the children.
import { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  HStack,
  Portal,
  Separator,
  Stack,
  Text,
} from '@chakra-ui/react';

import { logicalGraphNode, snapToNode } from './graph';
import {
  cancelNavigation,
  demoReset,
  directNavigateToNode,
  fetchRacks,
  navigateMission,
  pollMissionUntilDone,
  pickRack,
  SCHEDULER_ROBOTS,
  SchedulerConflictError,
  toSchedulerId,
  type MissionState,
} from './scheduler-api';
import type { RackMap, RobotGoal, SchedulerRobotId } from './types';
import { useMapImage } from './use-map-image';
import { useVdaState } from './use-vda-state';
import {
  pickRackJackDone,
  sortPickRackPoints,
  type PickRackPointOption,
} from './components/constants';
import { ConflictBanner } from './components/conflict-banner';
import { DirectNavigateCard } from './components/direct-navigate-card';
import { MapCanvas } from './components/map-canvas';
import { NavControls } from './components/nav-controls';
import { RobotCards, type PickRackSelection } from './components/robot-cards';
import { TaskCallout } from './components/task-callout';
import { notifyTask, TaskToaster } from './components/task-toaster';

interface NavConflict {
  detail: string;
  robotId: SchedulerRobotId;
  pendingGoal?: string;
}

export function VdaVisualiser() {
  const { map, agvs, status } = useVdaState();
  const mapImage = useMapImage();
  const [rotated, setRotated] = useState(true);

  const [selectedRobot, setSelectedRobot] = useState<SchedulerRobotId | null>(
    null,
  );
  const [goals, setGoals] = useState<
    Partial<Record<SchedulerRobotId, RobotGoal>>
  >({});
  const [racks, setRacks] = useState<RackMap>({});
  const [applying, setApplying] = useState(false);
  const [cancellingRobot, setCancellingRobot] =
    useState<SchedulerRobotId | null>(null);
  const [clearingConflict, setClearingConflict] = useState(false);
  const [conflict, setConflict] = useState<NavConflict | null>(null);
  const [demoResetOpen, setDemoResetOpen] = useState(false);
  const [demoResetting, setDemoResetting] = useState(false);

  useEffect(() => {
    fetchRacks().then(setRacks);
  }, []);

  // Rack buttons are parsed straight from the master's GET /map stations — no
  // robot connection or scheduler call needed. The pick_rack call resolves the
  // pose by station id server-side, so the buttons only need id/label/nodeId.
  const pickRackPoints = useMemo<readonly PickRackPointOption[]>(() => {
    const stations = map?.stations;
    if (!stations?.length) return [];
    return sortPickRackPoints(
      stations
        .filter(
          (s) => s.station_name.startsWith('Rack_') && s.node_ids.length > 0,
        )
        .map((s) => ({
          id: s.station_name,
          label: s.station_name.replace(/^Rack_/, ''),
          nodeId: s.node_ids[0],
          x: s.x,
          y: s.y,
          ori: 0,
        })),
    );
  }, [map?.stations]);

  // Pickup/dropoff-only missions: jack hold (pickup) or down (dropoff) means done
  // even before GET /demo/mission flips to completed.
  useEffect(() => {
    setGoals((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const robot of Object.keys(prev) as SchedulerRobotId[]) {
        const goal = prev[robot];
        if (
          !goal?.applied ||
          !goal.pickRackMode ||
          goal.pickRackMode === 'full'
        ) {
          continue;
        }
        const agv = agvs.find((a) => a.robot_id === robot);
        if (agv && pickRackJackDone(goal.pickRackMode, agv.jack_state)) {
          delete next[robot];
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [agvs]);

  const selectRobot = (id: SchedulerRobotId) => {
    setSelectedRobot((prev) => (prev === id ? null : id));
  };

  const pickNode = (nodeId: string) => {
    if (!selectedRobot) {
      notifyTask(
        'info',
        'Pick a robot first',
        'Then click a node to set its goal.',
      );
      return;
    }
    setGoals((prev) => {
      const current = prev[selectedRobot];
      if (current?.applied) return prev;
      if (current?.node === nodeId) return prev;
      return {
        ...prev,
        [selectedRobot]: { node: nodeId, applied: false },
      };
    });
  };

  const clearGoals = () => {
    setGoals({});
    setSelectedRobot(null);
    setConflict(null);
  };

  // Keyboard shortcuts: Esc clears the selection (same as the Clear button),
  // Enter applies pending goals (same as the Apply button).
  useEffect(() => {
    const hasPending = (Object.keys(goals) as SchedulerRobotId[]).some(
      (r) => goals[r] != null && !goals[r]!.applied,
    );
    const onKeyDown = (e: KeyboardEvent) => {
      // Let an open dialog handle its own keys.
      if (demoResetOpen) return;
      if (e.key === 'Escape') {
        // Only clear when something is selected.
        if (!selectedRobot && Object.keys(goals).length === 0 && !conflict) {
          return;
        }
        clearGoals();
      } else if (e.key === 'Enter') {
        // Mirror the Apply button: only when there's a pending goal and idle.
        if (!hasPending || applying) return;
        void applyGoals();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [demoResetOpen, selectedRobot, goals, conflict, applying]);

  const unapplyRobotGoal = (robotId: SchedulerRobotId) => {
    setGoals((prev) => {
      const goal = prev[robotId];
      if (!goal) return prev;
      return { ...prev, [robotId]: { ...goal, applied: false } };
    });
  };

  const notifyMissionOutcome = (
    robotId: SchedulerRobotId,
    final: MissionState,
  ) => {
    if (final.status === 'completed') {
      notifyTask(
        'success',
        'Mission complete',
        final.detail ?? `${robotId} finished`,
      );
      setGoals((prev) => {
        const next = { ...prev };
        delete next[robotId];
        return next;
      });
      return;
    }
    if (final.status === 'error') {
      const leg = final.legs.find((l) => l.status === 'error');
      const msg = final.detail ?? leg?.detail ?? `${robotId} mission failed`;
      notifyTask('error', 'Mission failed', msg);
      unapplyRobotGoal(robotId);
      return;
    }
    if (final.status === 'cancelled') {
      notifyTask('info', 'Mission cancelled', final.detail ?? robotId);
      setGoals((prev) => {
        const next = { ...prev };
        delete next[robotId];
        return next;
      });
    }
  };

  const watchMission = (robotId: SchedulerRobotId) => {
    void pollMissionUntilDone(robotId)
      .then((final) => notifyMissionOutcome(robotId, final))
      .catch((err) =>
        notifyTask(
          'error',
          'Mission status lost',
          `${robotId}: ${String(err)}`,
        ),
      );
  };

  const applyGoals = async () => {
    const pending = (Object.keys(goals) as SchedulerRobotId[]).filter(
      (r) => goals[r] != null && !goals[r]!.applied,
    );
    if (pending.length === 0) {
      notifyTask('info', 'No new goals to apply');
      return;
    }
    setApplying(true);
    setConflict(null);

    const dispatched: SchedulerRobotId[] = [];
    let firstConflict: NavConflict | null = null;

    for (const robotId of pending) {
      const goalNode = goals[robotId]!.node;
      try {
        await navigateMission(robotId, [goalNode], false);
        dispatched.push(robotId);
      } catch (err) {
        if (err instanceof SchedulerConflictError) {
          firstConflict ??= {
            detail: err.detail,
            robotId: err.robotId ?? robotId,
            pendingGoal: goalNode,
          };
        } else {
          notifyTask('error', 'Apply failed', String(err));
          setApplying(false);
          return;
        }
      }
    }

    if (dispatched.length > 0) {
      setGoals((prev) => {
        const next = { ...prev };
        for (const r of dispatched) {
          if (next[r]) next[r] = { ...next[r]!, applied: true };
        }
        return next;
      });
    }

    if (firstConflict) {
      setConflict(firstConflict);
      if (dispatched.length > 0) {
        notifyTask(
          'warning',
          'Partial apply',
          `${dispatched.join(', ')} dispatched; ` +
            `${firstConflict.robotId} blocked — use Clear conflict.`,
        );
      }
    } else if (dispatched.length > 0) {
      notifyTask(
        'info',
        'Mission running',
        dispatched.map((r) => `${r} → ${goals[r]!.node}`).join('; '),
      );
    }
    for (const robotId of dispatched) {
      watchMission(robotId);
    }
    setApplying(false);
  };

  const cancelNav = async (robotId: SchedulerRobotId) => {
    setCancellingRobot(robotId);
    try {
      await cancelNavigation(robotId);
      setGoals((prev) => {
        const next = { ...prev };
        delete next[robotId];
        return next;
      });
      if (conflict?.robotId === robotId) {
        setConflict(null);
      }
      notifyTask(
        'info',
        'Stop & reset complete',
        `${robotId} — motion stopped, mission and MAPF state cleared`,
      );
    } catch (err) {
      notifyTask('error', 'Stop & reset failed', String(err));
    } finally {
      setCancellingRobot(null);
    }
  };

  const runDemoReset = async () => {
    setDemoResetting(true);
    try {
      const result = await demoReset();
      clearGoals();
      const stopped = result.robots.filter((r) => r.robot_stopped).length;
      notifyTask(
        'success',
        'Stop & reset all complete',
        `${result.robots.length} robot(s) cleared; ${stopped} stopped; MAPF planner reset`,
      );
      setDemoResetOpen(false);
    } catch (err) {
      notifyTask('error', 'Stop & reset all failed', String(err));
    } finally {
      setDemoResetting(false);
    }
  };

  const resetToNode = async (robotId: SchedulerRobotId, nodeId: string) => {
    try {
      await directNavigateToNode(robotId, nodeId);
      notifyTask(
        'success',
        'Force navigate dispatched',
        `${robotId} → ${nodeId}`,
      );
    } catch (err) {
      notifyTask('error', 'Navigate failed', String(err));
      throw err;
    }
  };

  // Spellbook pick_rack from an AutoXing robot card (no MAPF / map nodes).
  const runPickRack = async (
    robotId: SchedulerRobotId,
    selection: PickRackSelection,
  ) => {
    if (!robotId.startsWith('autoxing')) {
      notifyTask(
        'error',
        'Pick rack not supported',
        `${robotId} has no pick row`,
      );
      return;
    }
    const routeLabel =
      selection.mode === 'pickup'
        ? `pick up @ ${selection.pickupLabel}`
        : selection.mode === 'dropoff'
          ? `drop off @ ${selection.putdownLabel}`
          : `${selection.pickupLabel} → ${selection.putdownLabel}`;
    setConflict(null);
    try {
      await pickRack(
        robotId,
        selection.mode,
        selection.mode !== 'dropoff' ? selection.pickup : undefined,
        selection.mode !== 'pickup' ? selection.putdown : undefined,
      );
      setGoals((prev) => ({
        ...prev,
        [robotId]: {
          node: routeLabel,
          applied: true,
          pickRackMode: selection.mode,
        },
      }));
      notifyTask('info', 'Pick rack running', `${robotId}: ${routeLabel}`);
      watchMission(robotId);
    } catch (err) {
      if (err instanceof SchedulerConflictError) {
        setConflict({
          detail: err.detail,
          robotId,
          pendingGoal: routeLabel,
        });
      } else {
        notifyTask('error', 'Pick rack failed', String(err));
      }
    }
  };

  const clearConflict = async () => {
    if (!conflict) return;
    setClearingConflict(true);
    try {
      await cancelNavigation(conflict.robotId);
      setGoals((prev) => {
        const next = { ...prev };
        delete next[conflict.robotId];
        return next;
      });
      const pendingGoal = conflict.pendingGoal;
      setConflict(null);
      if (pendingGoal) {
        await navigateMission(conflict.robotId, [pendingGoal], false);
        setGoals((prev) => ({
          ...prev,
          [conflict.robotId]: { node: pendingGoal, applied: true },
        }));
        notifyTask(
          'info',
          'Mission running',
          `${conflict.robotId} → ${pendingGoal}`,
        );
        watchMission(conflict.robotId);
      } else {
        notifyTask('info', 'Conflict cleared', `${conflict.robotId}`);
      }
    } catch (err) {
      if (err instanceof SchedulerConflictError) {
        setConflict({
          detail: err.detail,
          robotId: err.robotId ?? conflict.robotId,
          pendingGoal: conflict.pendingGoal,
        });
      }
      notifyTask('error', 'Clear conflict failed', String(err));
    } finally {
      setClearingConflict(false);
    }
  };

  const activeTasks = (Object.keys(goals) as SchedulerRobotId[]).flatMap(
    (robot) => {
      const goal = goals[robot];
      if (!goal?.applied) return [];
      if (goal.pickRackMode && goal.pickRackMode !== 'full') {
        const agv = agvs.find((a) => toSchedulerId(a) === robot);
        if (agv && pickRackJackDone(goal.pickRackMode, agv.jack_state)) {
          return [];
        }
        return [`${robot} → ${goal.node}`];
      }
      const agv = agvs.find((a) => toSchedulerId(a) === robot);
      const current = logicalGraphNode(
        agv?.last_node_id ??
          (agv?.has_pose && agv.x != null && agv.y != null
            ? snapToNode(agv.x, agv.y, map?.nodes ?? [])
            : null),
        racks,
      );
      if (current === goal.node) return [];
      return [`${robot} → ${goal.node}`];
    },
  );

  return (
    <Stack gap={6} py={4}>
      {/* Mission-pipeline events surface as top-left toasts (see TaskToaster). */}
      <TaskToaster />

      {conflict && (
        <ConflictBanner
          detail={conflict.detail}
          robotId={conflict.robotId}
          goalNode={conflict.pendingGoal}
          clearing={clearingConflict}
          onClear={() => void clearConflict()}
          onDismiss={() => setConflict(null)}
        />
      )}

      <Flex
        gap={4}
        align="stretch"
        direction={{ base: 'column', xl: 'row' }}
        h={{ base: 'auto', xl: 'calc(100vh - 200px)' }}
        minH="440px"
      >
        <Box flex="1" minW={0} h={{ base: '60vh', xl: '100%' }}>
          <MapCanvas
            map={map}
            agvs={agvs}
            rotated={rotated}
            onToggleRotate={() => setRotated((v) => !v)}
            mapImage={mapImage}
            goals={goals}
            racks={racks}
            selectedRobot={selectedRobot}
            onSelectRobot={selectRobot}
            onPickNode={pickNode}
          />
        </Box>
        {/* Right column: the live "task in progress" callout sits ABOVE the
            Robots card (outside it), then the bordered Robots panel fills the
            rest of the column. */}
        <Flex
          direction="column"
          gap={3}
          w={{ base: '100%', xl: '340px' }}
          flexShrink={0}
          h={{ base: 'auto', xl: '100%' }}
          minH={{ base: '440px', xl: undefined }}
        >
          <TaskCallout tasks={activeTasks} />
          <Flex
            direction="column"
            flex="1"
            minH={0}
            borderWidth="1px"
            borderColor="border.subtle"
            borderRadius="lg"
            overflow="hidden"
          >
            <HStack
              flexShrink={0}
              justify="space-between"
              align="center"
              px={3}
              py={2}
              borderBottomWidth="1px"
              borderColor="border.subtle"
              gap={2}
            >
              <Text fontSize="sm" fontWeight="semibold">
                Robots
              </Text>
              <HStack gap={2}>
                <Button
                  size="xs"
                  variant="outline"
                  colorPalette="red"
                  loading={demoResetting}
                  onClick={() => setDemoResetOpen(true)}
                >
                  Stop &amp; reset all
                </Button>
                <Badge
                  colorPalette={
                    status === 'connected'
                      ? 'green'
                      : status === 'connecting'
                        ? 'yellow'
                        : 'red'
                  }
                >
                  {status}
                </Badge>
              </HStack>
            </HStack>
            <Dialog.Root
              lazyMount
              open={demoResetOpen}
              onOpenChange={(e) => setDemoResetOpen(e.open)}
              role="alertdialog"
            >
              <Portal>
                <Dialog.Backdrop />
                <Dialog.Positioner>
                  <Dialog.Content>
                    <Dialog.Header>
                      <Dialog.Title>Stop &amp; reset all robots</Dialog.Title>
                    </Dialog.Header>
                    <Dialog.Body>
                      <Text fontSize="sm">
                        Stop every robot, clear all missions, reset the MAPF
                        planner, and clear any stuck (zombie) order so Apply
                        works again — no Docker restart needed.
                      </Text>
                    </Dialog.Body>
                    <Dialog.Footer>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={demoResetting}
                        onClick={() => setDemoResetOpen(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        colorPalette="red"
                        loading={demoResetting}
                        onClick={() => void runDemoReset()}
                      >
                        Stop &amp; reset all
                      </Button>
                    </Dialog.Footer>
                  </Dialog.Content>
                </Dialog.Positioner>
              </Portal>
            </Dialog.Root>
            <Box flex="1" overflowY="auto" minH={0} p={3}>
              <RobotCards
                agvs={agvs}
                goals={goals}
                selectedRobot={selectedRobot}
                cancellingRobot={cancellingRobot}
                onSelectRobot={selectRobot}
                onCancelRobot={(id) => void cancelNav(id)}
                onResetToNode={resetToNode}
                onPickRack={runPickRack}
                pickRackPoints={pickRackPoints}
              />
            </Box>
            <Box
              flexShrink={0}
              borderTopWidth="1px"
              borderColor="border.subtle"
              bg="bg.subtle"
              px={3}
              py={3}
              borderBottomRadius="lg"
            >
              <NavControls
                selectedRobot={selectedRobot}
                goals={goals}
                racks={racks}
                applying={applying}
                onSelectRobot={selectRobot}
                onApply={() => void applyGoals()}
                onClear={clearGoals}
                onStopReset={() =>
                  selectedRobot && void cancelNav(selectedRobot)
                }
                stopResetLoading={
                  selectedRobot != null && cancellingRobot === selectedRobot
                }
              />
            </Box>
          </Flex>
        </Flex>
      </Flex>

      <Separator />
      <Stack gap={1}>
        <Text fontSize="lg" fontWeight="bold">
          Direct Control
        </Text>
        <Text fontSize="sm" color="gray.500">
          Not using any map app — bypasses MAPF and sends master-frame X/Y (and
          optional θ) straight to the robot. AutoXing cards and Direct Control
          both include manual jack up / down. Reeman is navigate-only here.
        </Text>
      </Stack>
      <HStack align="stretch" gap={4} flexWrap="wrap">
        {(agvs.length > 0
          ? agvs.map((a) => ({ id: a.robot_id, label: a.robot_id }))
          : SCHEDULER_ROBOTS.map((r) => ({
              id: r as string,
              label: r as string,
            }))
        ).map(({ id, label }) => (
          <DirectNavigateCard key={id} robot={id} label={label} />
        ))}
      </HStack>
    </Stack>
  );
}

export default VdaVisualiser;
