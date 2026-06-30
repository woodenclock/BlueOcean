import { Box, Card, HStack, Stack, Text } from '@chakra-ui/react';

import type { RobotStatus } from '../robot-types';

type RobotStatusPanelProps = {
  robots: RobotStatus[];
};

function formatCoord(value: number) {
  return value.toFixed(3);
}

function getStatusColor(status: RobotStatus['status']) {
  if (status === 'blocked') return 'fg.error';
  if (status === 'moving') return 'blue.500';
  if (status === 'arrived') return 'green.500';
  return 'fg.muted';
}

export function RobotStatusPanel({ robots }: RobotStatusPanelProps) {
  return (
    <Card.Root
      size="sm"
      variant="outline"
      position="absolute"
      top="96px"
      right={3}
      zIndex={2}
      bg="bg/90"
      backdropFilter="blur(4px)"
      pointerEvents="auto"
      minW="240px"
      maxW="300px"
      maxH="calc(100% - 112px)"
      overflowY="auto"
    >
      <Card.Body gap={2.5} py={3}>
        <HStack justify="space-between" align="center">
          <Text fontSize="sm" fontWeight="semibold">
            Robots
          </Text>

          <Text fontSize="xs" color="fg.muted">
            {robots.length} total
          </Text>
        </HStack>

        {robots.length === 0 ? (
          <Text fontSize="xs" color="fg.muted" lineHeight="short">
            No robots loaded. Check that robot.glb is available and that the
            robot config API returns robots.
          </Text>
        ) : (
          <Stack gap={2}>
            {robots.map((robot) => (
              <Box
                key={robot.id}
                px={2}
                py={1.5}
                rounded="md"
                bg="bg.subtle"
                borderWidth="1px"
                borderColor="border.subtle"
              >
                <HStack justify="space-between" align="start" gap={3}>
                  <Box>
                    <Text fontSize="xs" fontWeight="semibold">
                      {robot.name}
                    </Text>

                    <Text fontSize="xs" color="fg.muted" fontFamily="mono">
                      {robot.id}
                    </Text>
                  </Box>

                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    textTransform="uppercase"
                    color={getStatusColor(robot.status)}
                  >
                    {robot.status}
                  </Text>
                </HStack>

                <Text mt={1} fontSize="xs" color="fg.muted" fontFamily="mono">
                  x {formatCoord(robot.position.x)} · y{' '}
                  {formatCoord(robot.position.y)} · z{' '}
                  {formatCoord(robot.position.z)}
                </Text>

                {robot.waypointCount !== undefined && (
                  <Text mt={1} fontSize="xs" color="fg.muted">
                    Waypoint {(robot.waypointIndex ?? 0) + 1}/
                    {robot.waypointCount}:{' '}
                    {robot.waypointLabel ?? robot.waypointId}
                  </Text>
                )}

                {robot.target && (
                  <Text mt={1} fontSize="xs" color="fg.muted" fontFamily="mono">
                    → x {formatCoord(robot.target.x)} · y{' '}
                    {formatCoord(robot.target.y)} · z{' '}
                    {formatCoord(robot.target.z)}
                  </Text>
                )}

                {robot.blockedBy && (
                  <Text mt={1} fontSize="xs" color="fg.error">
                    Blocked by {robot.blockedBy}
                  </Text>
                )}
              </Box>
            ))}
          </Stack>
        )}
      </Card.Body>
    </Card.Root>
  );
}

export default RobotStatusPanel;
