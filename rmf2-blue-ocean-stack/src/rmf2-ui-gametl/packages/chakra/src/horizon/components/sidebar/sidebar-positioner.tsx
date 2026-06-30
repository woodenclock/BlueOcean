import type { BoxProps } from '@chakra-ui/react';
import { Box, Flex } from '@chakra-ui/react';

export interface SidebarPositionerProps extends BoxProps {}

export function SidebarPositioner(props: SidebarPositionerProps) {
  const { children, ...rest } = props;
  const sidebarBg = { base: 'white', _dark: 'navy.800' };
  const shadow = {
    base: '14px 17px 40px 4px rgba(112, 144, 176, 0.08)',
    _dark: 'unset',
  };
  const variantChange = '0.2s linear';
  const sidebarMargins = '0px';

  return (
    <Box
      display={{ base: 'none', xl: 'block' }}
      position="fixed"
      m={sidebarMargins}
      bg={sidebarBg}
      transition={variantChange}
      w="300px"
      h="100%"
      overflowX="hidden"
      boxShadow={shadow}
      {...rest}
    >
      <Flex direction="column" height="100%">
        {children}
      </Flex>
    </Box>
  );
}
