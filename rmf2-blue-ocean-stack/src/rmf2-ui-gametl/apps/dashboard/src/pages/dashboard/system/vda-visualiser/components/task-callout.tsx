// "Task in progress" callout with a live, pulsing status dot (ping ring +
// solid core) — shown while robots are executing a navigation task.
import { Box, HStack, Stack, Text } from '@chakra-ui/react';

interface TaskCalloutProps {
  tasks: string[];
}

export function TaskCallout({ tasks }: TaskCalloutProps) {
  if (tasks.length === 0) return null;
  return (
    <HStack
      gap={3}
      px={4}
      py={3}
      borderWidth="1px"
      borderColor="teal.300"
      bg="teal.50"
      borderRadius="lg"
      borderLeftWidth="4px"
      borderLeftColor="teal.500"
    >
      {/* Live indicator: expanding ping ring behind a solid core. */}
      <Box position="relative" w="12px" h="12px" flexShrink={0}>
        <Box
          position="absolute"
          inset="0"
          borderRadius="full"
          bg="teal.400"
          animation="ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite"
        />
        <Box
          position="absolute"
          inset="0"
          borderRadius="full"
          bg="teal.500"
          animation="pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite"
        />
      </Box>
      <Stack gap={0}>
        <Text fontSize="sm" fontWeight="semibold" color="teal.700">
          Task in progress — robots are on the move
        </Text>
        <Text fontSize="xs" color="teal.700">
          {tasks.join('  ·  ')}
        </Text>
      </Stack>
    </HStack>
  );
}

export default TaskCallout;
