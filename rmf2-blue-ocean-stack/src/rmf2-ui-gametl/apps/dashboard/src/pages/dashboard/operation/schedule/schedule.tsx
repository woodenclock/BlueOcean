import { useState, useEffect } from 'react';
import { Box, Button, Flex, Spacer, Text } from '@chakra-ui/react';
import { Horizon } from '@rmf2-ui/chakra';
import Card = Horizon.Card;
import type { RTS } from '@rmf2-ui/data';
import { RTOConfig, LauncherConfig } from '@/clients';
import { toaster } from '@/components/ui/toaster';
import { Pending } from '@/components/pending';
import { DateTimeSelector } from './components/date-time-selector';
import { useRTSClient } from '@/clients/rts';
import { Schedule } from '@/components/schedule';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';

export function SchedulePage() {
  // Chakra Color Mode
  const currentDate = new Date();
  const rtsClient = useRTSClient();
  const queryClient = useQueryClient();
  const [refetchInterval, setRefetchInterval] = useState<false | number>(false);
  const {
    isPending: isPendingGetSchedule,
    data: schedule,
    error: errorGetSchedule,
    isError: isErrorGetSchedule,
    refetch: refetchGetSchedule,
  } = useQuery({
    queryKey: ['RTSSchedule'],
    queryFn: async (): Promise<RTS.Schedule> => {
      const schedule = await rtsClient.getSchedule({ offset: 0, limit: 100 });
      return schedule;
    },
    staleTime: 5 * 1000,
    gcTime: 0,
    refetchInterval,
  });

  const sendTaskRTS = async () => {
    // TODO(anyone): fix response header to remove the try-catch
    try {
      await fetch(LauncherConfig.BASE + '/send_task', {
        method: 'POST',
        headers: {
          Accept: '*',
        },
      });
    } catch (e) {
      console.error(e);
    }
  };

  const sendTaskRTO = async () => {
    // TODO(anyone): fix response header to remove the try-catch
    try {
      await fetch(RTOConfig.BASE + '/send_task', {
        method: 'POST',
        headers: {
          Accept: '*',
        },
      });
    } catch (e) {
      console.error(e);
    }
  };

  const sendTask = async () => {
    await sendTaskRTS();
    await sendTaskRTO();
    await new Promise((resolve) => setTimeout(resolve, 5 * 1000));
  };

  const { mutateAsync: sendTaskMutation, error: errorSendTask } = useMutation({
    mutationFn: sendTask,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['RTSSchedule'],
      });
    },
  });

  const optimizeSchedule = async () => {
    return await rtsClient.optimize({ optimizationDuration: 60 * 60 * 24 });
  };

  const {
    mutateAsync: optimzeScheduleMutation,
    isPending: optimizeSchedulePending,
  } = useMutation({
    mutationFn: optimizeSchedule,
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ['RTSSchedule'],
      });

      toaster.create({
        title: 'Success Optimize Schedule',
        description: `${data}`,
        type: 'success',
        duration: 10 * 1000,
        closable: true,
      });
    },
    onError: (error) => {
      toaster.create({
        title: 'Failed Optimize Schedule',
        description: `${error.message}`,
        type: 'error',
        duration: 10 * 1000,
        closable: true,
      });
    },
  });

  async function refreshSchedule() {
    await refetchGetSchedule();
  }

  const {
    mutateAsync: refreshScheduleMutation,
    isPending: refreshSchedulePending,
  } = useMutation({
    mutationFn: refreshSchedule,
  });

  async function deleteTask(uuid: string) {
    return await rtsClient.deleteTask({ uuid: uuid });
  }

  const { mutateAsync: deleteTaskMutation, isPending: deleteTaskPending } =
    useMutation({
      mutationFn: deleteTask,
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ['RTSSchedule'],
        });
      },
      onError: (error) => {
        toaster.create({
          title: 'Error Deleting Task',
          description: `${error}`,
          type: 'error',
          duration: 10 * 1000,
          closable: true,
        });
      },
    });

  const convertToCSV = (tasks: RTS.Task[]) => {
    if (tasks.length === 0) {
      return '';
    }
    const header = Object.keys(tasks[0]);
    const rows = tasks.map((task) =>
      header
        .map((field) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          return JSON.stringify((task as Record<string, any>)[field]);
        })
        .join(','),
    );
    return [header.join(','), ...rows].join('\n');
  };

  const downloadCSV = () => {
    if (!schedule) {
      return;
    }

    const csv = convertToCSV(schedule.tasks);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'task-data.csv';
    link.click();
  };

  useEffect(() => {
    if (!isErrorGetSchedule) {
      return;
    }

    const toasterId = errorGetSchedule.name;

    if (toaster.isVisible(toasterId)) {
      return;
    }

    toaster.create({
      id: toasterId,
      title: 'Error Getting Schedule',
      description: `${errorGetSchedule.name}: ${errorGetSchedule.message}`,
      type: 'error',
      duration: 10 * 1000,
      closable: true,
    });
  }, [isErrorGetSchedule, errorGetSchedule]);

  return (
    <Box>
      <Card flexDirection="column" gap="5px" p="25px">
        <Flex justifyContent="space-between" align="center">
          <Flex align="center" gap="20px">
            <Text fontSize="22px" fontWeight="700" lineHeight="100%">
              Schedule Viewer
            </Text>
            <Button
              onClick={() => {
                const promise = sendTaskMutation();
                toaster.promise(promise, {
                  success: {
                    title: 'Successfully Send Task',
                    description: 'Work Order',
                    duration: 5000,
                    closable: true,
                  },
                  error: {
                    title: 'Error Send Task',
                    description: `${errorSendTask?.name}: ${errorSendTask?.message}`,
                    duration: 5000,
                    closable: true,
                  },
                  loading: {
                    title: 'Sending Task...',
                    description: 'Work Order',
                  },
                });
              }}
              colorPalette="blue"
              variant="solid"
              disabled={isErrorGetSchedule}
            >
              Send Preset Task
            </Button>
          </Flex>
        </Flex>
        {/* Schedule Viewer */}
        <Schedule.Root schedule={schedule}>
          {/* Schedule Tabs */}
          <Schedule.TabsRoot>
            {/* Schedule Tabs Control */}
            <Schedule.TabsControl />

            {/* Schedule Tabs Schedule Display */}
            <Schedule.TabsContentSchedule>
              {/* Control Panel */}
              <Schedule.ControlPanel>
                <Schedule.AddButton disabled={schedule === undefined} />
                <Schedule.DownloadButton
                  onClick={downloadCSV}
                  disabled={schedule === undefined}
                />
                <Schedule.RefreshButton
                  onClick={async () => await refreshScheduleMutation()}
                  loading={refreshSchedulePending}
                />
                <Schedule.LiveToggle
                  onToggleLive={(live) => {
                    setRefetchInterval(live ? 1000 : false);
                  }}
                />
                <Schedule.OptimizeButton
                  onClick={async () => await optimzeScheduleMutation()}
                  loading={optimizeSchedulePending}
                />
                <Spacer />

                <DateTimeSelector currentDate={currentDate} />
              </Schedule.ControlPanel>
              <Schedule.Gantt />
            </Schedule.TabsContentSchedule>

            {/* Schedule Tabs Process Display */}
            <Schedule.TabsContentProcess>
              <Schedule.Process />
            </Schedule.TabsContentProcess>
          </Schedule.TabsRoot>

          {/* Task Dialog Popover */}
          <Schedule.TaskDialog placement="center">
            <Schedule.TaskDialogControlPanel
              onDelete={async (event) =>
                await deleteTaskMutation(event.task.id)
              }
              isDeleting={deleteTaskPending}
            />
          </Schedule.TaskDialog>
        </Schedule.Root>
        {isPendingGetSchedule && (
          <Pending.Root>
            <Pending.Overlay />
            <Pending.Spinner />
          </Pending.Root>
        )}
      </Card>
    </Box>
  );
}
