import {
  createContext,
  useCallback,
  useContext,
  useState,
  useEffect,
} from 'react';
import type { RTS } from '@rmf2-ui/data';

interface TimeViewWindow {
  start: Date;
  end: Date;
}

export interface UseScheduleProps {
  schedule?: RTS.Schedule;
  live?: boolean;
  timeViewWindow?: TimeViewWindow;
}

export function useSchedule(props: UseScheduleProps) {
  const {
    schedule,
    live: defaultLive,
    timeViewWindow: defaultTimeViewWindow,
  } = props;
  const [tabValue, setTabValue] = useState<string | null>('schedule');
  const [live, setLive] = useState<boolean>(defaultLive ?? false);
  const [timeViewWindow, setTimeViewWindow] = useState<
    TimeViewWindow | undefined
  >(defaultTimeViewWindow);
  const [viewTask, setViewTask] = useState<RTS.Task | undefined>(undefined);
  const [viewProcess, setViewProcess] = useState<RTS.Process | undefined>(
    undefined,
  );
  const [taskDialogOpen, setTaskDialogOpen] = useState<boolean>(false);

  return {
    schedule,
    tabValue,
    setTabValue,
    live,
    setLive,
    timeViewWindow,
    setTimeViewWindow,
    viewTask,
    setViewTask,
    viewProcess,
    setViewProcess,
    taskDialogOpen,
    setTaskDialogOpen,
  };
}

export type UseScheduleReturn = ReturnType<typeof useSchedule>;

export const ScheduleContext = createContext<UseScheduleReturn | undefined>(
  undefined,
);

const useScheduleContext = () => {
  const horizonScheduleContext = useContext(ScheduleContext);
  if (horizonScheduleContext === undefined) {
    throw new Error(
      'useScheduleContext must be inside a ScheduleContext.Provider',
    );
  }
  return horizonScheduleContext;
};

export function useScheduleTabsRoot() {
  const { tabValue, setTabValue } = useScheduleContext();

  return {
    tabValue,
    setTabValue,
  };
}

export function useScheduleGantt() {
  const { schedule, setViewTask, setTaskDialogOpen } = useScheduleContext();

  const openTaskViewDialog = useCallback(
    (taskId: string) => {
      if (schedule === undefined) {
        return;
      }

      const currentTask = schedule.tasks.find((task) => task.id === taskId);
      if (currentTask !== undefined) {
        setViewTask(currentTask);
      }
      setTaskDialogOpen(true);
    },
    [schedule, setViewTask, setTaskDialogOpen],
  );

  return {
    tasks: schedule === undefined ? [] : schedule.tasks,
    openTaskViewDialog,
  };
}

export function useScheduleTaskDialog() {
  const { viewTask, taskDialogOpen, setTaskDialogOpen } = useScheduleContext();

  return {
    viewTask,
    open: taskDialogOpen,
    setOpen: setTaskDialogOpen,
  };
}

export function useScheduleControlPanel() {
  const { schedule, live, setLive, timeViewWindow, setTimeViewWindow } =
    useScheduleContext();

  return {
    schedule,
    live,
    setLive,
    timeViewWindow,
    setTimeViewWindow,
  };
}

export interface UseScheduleLiveToggleProps {
  live?: boolean;
}

export function useScheduleLiveToggle(props: UseScheduleLiveToggleProps) {
  const { schedule, live, setLive } = useScheduleContext();
  const { live: liveExternal } = props;

  useEffect(() => {
    if (liveExternal === undefined) {
      return;
    }

    // TODO(Briancbn): switch to useCallback?
    setLive(liveExternal);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveExternal]);

  return {
    disabled: schedule === undefined,
    live,
    setLive,
  };
}

export function useScheduleRefreshButton() {
  const { schedule, live } = useScheduleContext();

  return {
    disabled: schedule === undefined,
    loading: live,
  };
}

export function useScheduleProcess() {
  const { schedule, viewProcess, setViewProcess } = useScheduleContext();

  return {
    schedule,
    viewProcess,
    setViewProcess,
  };
}
