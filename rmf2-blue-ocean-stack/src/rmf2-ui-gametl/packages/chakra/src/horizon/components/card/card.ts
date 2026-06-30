import type { HTMLChakraProps } from '@chakra-ui/react';
import { chakra } from '@chakra-ui/react';

export interface CardProps extends HTMLChakraProps<'div'> {}

export const Card = chakra('div', {
  base: {
    p: '20px',
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    position: 'relative',
    borderRadius: '20px',
    minWidth: '0px',
    wordWrap: 'break-word',
    bg: { base: '#ffffff', _dark: 'navy.800' },
    backgroundClip: 'border-box',
  },
});

Card.displayName = 'Horizon.Card';
