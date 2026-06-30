import type { BoxProps } from '@chakra-ui/react';
import { Box } from '@chakra-ui/react';

export interface SidebarContentProps extends BoxProps {}

export function SidebarContent(props: SidebarContentProps) {
  const { children, ...rest } = props;
  // SIDEBAR
  return (
    <Box mt="8px" mb="auto" ps="20px" {...rest}>
      {children}
    </Box>
  );
}

export default SidebarContent;
