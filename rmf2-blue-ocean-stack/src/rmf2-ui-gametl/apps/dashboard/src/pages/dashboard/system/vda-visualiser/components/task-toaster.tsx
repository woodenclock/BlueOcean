'use client';

// Toasts for mission-pipeline events (MAPF planner, task-orchestrator,
// scheduler). Anchored to the TOP-LEFT of the *content* area: offset past the
// fixed sidebar (300px on xl, none below xl) so toasts never overlap it, and
// below the navbar. At most 3 stack at once; each auto-dismisses (with the
// built-in slide/fade) and can be closed early via the X.
import {
  Toaster as ChakraToaster,
  Portal,
  Spinner,
  Stack,
  Toast,
  createToaster,
} from '@chakra-ui/react';

export const taskToaster = createToaster({
  placement: 'top-start',
  max: 3,
  pauseOnPageIdle: true,
});

type NotifyType = 'info' | 'success' | 'warning' | 'error';

// Thin wrapper so callers don't repeat closable/duration on every event.
export function notifyTask(
  type: NotifyType,
  title: string,
  description?: string,
) {
  taskToaster.create({
    type,
    title,
    description,
    closable: true,
    duration: 5000,
  });
}

export function TaskToaster() {
  return (
    <Portal>
      <ChakraToaster
        toaster={taskToaster}
        insetInlineStart={{ base: '4', xl: '316px' }}
        insetBlockStart={{ base: '88px', md: '100px' }}
      >
        {(toast) => (
          <Toast.Root width={{ base: 'auto', md: 'sm' }} borderRadius="10px">
            {toast.type === 'loading' ? (
              <Spinner size="sm" color="blue.solid" />
            ) : (
              <Toast.Indicator />
            )}
            <Stack gap="1" flex="1" maxWidth="100%">
              {toast.title && <Toast.Title>{toast.title}</Toast.Title>}
              {toast.description && (
                <Toast.Description>{toast.description}</Toast.Description>
              )}
            </Stack>
            {toast.closable && <Toast.CloseTrigger />}
          </Toast.Root>
        )}
      </ChakraToaster>
    </Portal>
  );
}

export default TaskToaster;
