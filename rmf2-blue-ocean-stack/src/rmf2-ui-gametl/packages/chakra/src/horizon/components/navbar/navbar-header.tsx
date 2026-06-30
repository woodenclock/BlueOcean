import type { StackProps } from '@chakra-ui/react';
import { Stack } from '@chakra-ui/react';

export interface NavbarHeaderProps extends StackProps {}

export function NavbarHeader(props: NavbarHeaderProps) {
  const { children, ...rest } = props;
  return (
    <Stack mb={{ base: '8px', md: '0px' }} {...rest}>
      {children}
    </Stack>
  );
}
