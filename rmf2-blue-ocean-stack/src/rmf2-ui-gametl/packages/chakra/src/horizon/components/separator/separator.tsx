import type { FlexProps } from '@chakra-ui/react';
import { Flex } from '@chakra-ui/react';

export interface HSeparatorProps extends FlexProps {}

export const HSeparator = (props: HSeparatorProps) => {
  const { ...rest } = props;
  return <Flex h="1px" w="100%" bg="rgba(135, 140, 189, 0.3)" {...rest} />;
};

export type VSeparatorProps = HSeparatorProps;

export const VSeparator = (props: VSeparatorProps) => {
  const { ...rest } = props;
  return <Flex w="1px" bg="rgba(135, 140, 189, 0.3)" {...rest} />;
};
