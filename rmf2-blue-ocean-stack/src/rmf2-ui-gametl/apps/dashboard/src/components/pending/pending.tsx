import { Spinner, chakra } from '@chakra-ui/react';
import type { HTMLChakraProps, SpinnerProps } from '@chakra-ui/react';

export interface PendingRootProps extends HTMLChakraProps<'div'> {}

export const PendingRoot = chakra('div', {
  base: {
    position: 'absolute',
    inset: '0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
});

PendingRoot.displayName = 'Pending.Root';

export interface PendingOverlayProps extends HTMLChakraProps<'div'> {}

export const PendingOverlay = chakra('div', {
  base: {
    position: 'absolute',
    inset: '0',
    bg: { base: 'bg/80', _dark: 'bg/70' },
  },
});

PendingOverlay.displayName = 'Pending.Overlay';

export interface PendingSpinnerProps extends SpinnerProps {}
export function PendingSpinner(props: PendingSpinnerProps) {
  return <Spinner color="brand.500" size="xl" borderWidth="5px" {...props} />;
}
