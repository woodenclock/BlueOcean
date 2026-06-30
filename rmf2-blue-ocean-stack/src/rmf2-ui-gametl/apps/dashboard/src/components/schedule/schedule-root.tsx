import { useMemo } from 'react';
import type { BoxProps } from '@chakra-ui/react';
import { Box } from '@chakra-ui/react';
import type { UseScheduleProps } from './use-schedule';
import { useSchedule, ScheduleContext } from './use-schedule';

export interface ScheduleRootProps extends BoxProps, UseScheduleProps {}

export function ScheduleRoot(props: ScheduleRootProps) {
  const { children, ...rest } = props as BoxProps;

  const { ...context } = useSchedule(props as UseScheduleProps);
  const ctx = useMemo(() => ({ ...context }), [context]);

  return (
    <Box {...rest}>
      <ScheduleContext value={ctx}>{children}</ScheduleContext>
    </Box>
  );
}

export default ScheduleRoot;
