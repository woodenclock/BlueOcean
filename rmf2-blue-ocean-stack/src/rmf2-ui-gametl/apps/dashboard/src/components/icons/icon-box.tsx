import { ReactNode } from 'react';
import type { FlexProps } from '@chakra-ui/react';
import { Flex } from '@chakra-ui/react';

export interface IconBoxProps extends FlexProps {
  icon: ReactNode | string;
}

export function IconBox(props: IconBoxProps) {
  const { icon, ...rest } = props;

  return (
    <Flex
      alignItems={'center'}
      justifyContent={'center'}
      borderRadius="6px"
      {...rest}
    >
      {icon}
    </Flex>
  );
}
