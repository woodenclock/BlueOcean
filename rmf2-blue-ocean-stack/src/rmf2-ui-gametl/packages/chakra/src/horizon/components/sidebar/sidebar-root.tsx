import type { BoxProps } from '@chakra-ui/react';
import { Box } from '@chakra-ui/react';
import type { UseSidebarProps } from './use-sidebar';
import { useSidebar, SidebarContext } from './use-sidebar';

export interface SidebarRootProps extends BoxProps, UseSidebarProps {}

export function SidebarRoot(props: SidebarRootProps) {
  const { children, routes, collapsed, ...rest } = props;

  const defaultValue = useSidebar({ routes, collapsed });

  // Chakra Color Mode

  // SIDEBAR
  return (
    <Box {...rest}>
      <SidebarContext value={defaultValue}>{children}</SidebarContext>
    </Box>
  );
}

export default SidebarRoot;
