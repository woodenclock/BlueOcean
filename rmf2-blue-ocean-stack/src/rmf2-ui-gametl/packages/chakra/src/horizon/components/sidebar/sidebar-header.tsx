import type { FlexProps } from '@chakra-ui/react';
import { Flex } from '@chakra-ui/react';
import { HSeparator } from '@/horizon/components';

export interface SidebarHeaderProps extends FlexProps {}

export function SidebarHeader(props: FlexProps) {
  const { children, ...rest } = props;
  return (
    <Flex
      pt="25px"
      mb="20px"
      alignItems="center"
      flexDirection="column"
      {...rest}
    >
      {children}
      <HSeparator />
    </Flex>
  );
}
