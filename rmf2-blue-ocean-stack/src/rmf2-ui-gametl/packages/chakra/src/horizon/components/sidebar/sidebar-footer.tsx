import type { BoxProps } from '@chakra-ui/react';
import { Box } from '@chakra-ui/react';

export interface SidebarFooterProps extends BoxProps {}

export function SidebarFooter(props: SidebarFooterProps) {
  const { children, ...rest } = props;
  return (
    <Box
      ps="20px"
      pe={{ lg: '16px', '2xl': '20px' }}
      mt="60px"
      mb="40px"
      borderRadius="30px"
      {...rest}
    >
      {children}
    </Box>
  );
}

export default SidebarFooter;
