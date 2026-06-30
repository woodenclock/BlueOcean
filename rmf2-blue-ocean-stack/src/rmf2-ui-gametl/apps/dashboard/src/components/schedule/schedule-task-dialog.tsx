import { EventHandler, MouseEvent, ReactNode } from 'react';
import type { DialogRootProps } from '@chakra-ui/react';
import {
  Button,
  Badge,
  CloseButton,
  DataList,
  Dialog,
  Flex,
  Tabs,
  Portal,
} from '@chakra-ui/react';
import type { RTS } from '@rmf2-ui/data';
import { useScheduleTaskDialog } from './use-schedule';

export interface ScheduleTaskDialogProps
  extends Omit<DialogRootProps, 'children'> {
  children?: ReactNode;
}

export function ScheduleTaskDialog(props: ScheduleTaskDialogProps) {
  const { children, ...rest } = props;

  const { viewTask: currentTask, open, setOpen } = useScheduleTaskDialog();

  const formatDate = (time: Date | undefined): string => {
    if (time === undefined) {
      return '-';
    }

    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(time);
  };

  const formatStatus = (statusText: string): ReactNode => {
    let badgeColor = 'darkGray';
    if (statusText === 'completed') {
      badgeColor = 'green';
    } else if (statusText === 'failed') {
      badgeColor = 'red';
    } else if (statusText === 'ongoing') {
      badgeColor = 'yellow';
    }
    return (
      <Badge colorPalette={badgeColor}>
        {statusText === '' ? 'unknown' : statusText}
      </Badge>
    );
  };

  return (
    <Dialog.Root
      lazyMount
      open={open}
      onOpenChange={(e) => setOpen(e.open)}
      {...rest}
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>Task</Dialog.Title>
            </Dialog.Header>

            <Dialog.Body>
              <Flex gap="20px" direction="column">
                {currentTask && (
                  <Tabs.Root
                    lazyMount
                    unmountOnExit
                    defaultValue="summary"
                    variant="subtle"
                  >
                    <Tabs.List rounded="13">
                      <Tabs.Trigger value="summary">Summary</Tabs.Trigger>
                      <Tabs.Trigger value="details">Details</Tabs.Trigger>
                    </Tabs.List>
                    <Tabs.Content value="summary" ms="3">
                      <DataList.Root orientation="horizontal">
                        <DataList.Item>
                          <DataList.ItemLabel>Description</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {currentTask?.description}
                          </DataList.ItemValue>
                        </DataList.Item>
                        <DataList.Item>
                          <DataList.ItemLabel>Type</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {currentTask.type}
                          </DataList.ItemValue>
                        </DataList.Item>
                        <DataList.Item>
                          <DataList.ItemLabel>Start Time</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {formatDate(currentTask.startTime)}
                          </DataList.ItemValue>
                        </DataList.Item>
                        <DataList.Item>
                          <DataList.ItemLabel>End Time</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {formatDate(currentTask.endTime)}
                          </DataList.ItemValue>
                        </DataList.Item>
                        <DataList.Item
                          color={
                            currentTask.deadline === undefined ||
                            currentTask.endTime === undefined ||
                            currentTask?.deadline >= currentTask.endTime
                              ? 'inherit'
                              : 'red'
                          }
                        >
                          <DataList.ItemLabel>Deadline</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {formatDate(currentTask?.deadline)}
                          </DataList.ItemValue>
                        </DataList.Item>
                        <DataList.Item>
                          <DataList.ItemLabel>Assigned to</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {currentTask.resourceId}
                          </DataList.ItemValue>
                        </DataList.Item>
                        <DataList.Item>
                          <DataList.ItemLabel>Status</DataList.ItemLabel>
                          <DataList.ItemValue>
                            {formatStatus(currentTask.status)}
                          </DataList.ItemValue>
                        </DataList.Item>
                        {currentTask.taskDetails.coordinates && (
                          <DataList.Item>
                            <DataList.ItemLabel>
                              Target Location
                            </DataList.ItemLabel>
                            <DataList.ItemValue>
                              {currentTask.taskDetails.coordinates as string}
                            </DataList.ItemValue>
                          </DataList.Item>
                        )}
                        {currentTask.taskDetails.resource_type && (
                          <DataList.Item>
                            <DataList.ItemLabel>
                              Resource Type
                            </DataList.ItemLabel>
                            <DataList.ItemValue>
                              {currentTask.taskDetails.resource_type as string}
                            </DataList.ItemValue>
                          </DataList.Item>
                        )}
                      </DataList.Root>
                    </Tabs.Content>
                    <Tabs.Content value="details" ms="3">
                      <DataList.Root orientation="horizontal">
                        {Object.keys(currentTask).map((label) => (
                          <DataList.Item key={label}>
                            <DataList.ItemLabel>{label}</DataList.ItemLabel>
                            <DataList.ItemValue flex="1">
                              {JSON.stringify(
                                Object.getOwnPropertyDescriptor(
                                  currentTask,
                                  label,
                                )?.value,
                                null,
                                2,
                              )}
                            </DataList.ItemValue>
                          </DataList.Item>
                        ))}
                      </DataList.Root>
                    </Tabs.Content>
                  </Tabs.Root>
                )}
                {children}
              </Flex>
            </Dialog.Body>
            <Dialog.CloseTrigger asChild>
              <CloseButton size="sm" />
            </Dialog.CloseTrigger>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}

export interface DeleteEvent extends MouseEvent<HTMLButtonElement> {
  task: RTS.Task;
}

export interface ScheduleTaskDialogControlPanelProps {
  onDelete?: EventHandler<DeleteEvent>;
  isDeleting?: boolean;
  deleteDisabled?: boolean;
}

export function ScheduleTaskDialogControlPanel(
  props: ScheduleTaskDialogControlPanelProps,
) {
  const { onDelete, isDeleting, deleteDisabled } = props;
  const { viewTask: currentTask } = useScheduleTaskDialog();

  return (
    <>
      {currentTask && currentTask.status === '' && (
        <Flex gap="5%" justify="center">
          <Button w="45%" colorPalette="blue" variant="subtle">
            Edit
          </Button>
          <Button
            w="45%"
            colorPalette="red"
            variant="subtle"
            onClick={(event) => {
              if (onDelete === undefined) {
                return;
              }
              onDelete({
                task: currentTask,
                ...event,
              });
            }}
            loading={isDeleting}
            disabled={deleteDisabled}
          >
            Delete
          </Button>
        </Flex>
      )}
    </>
  );
}
