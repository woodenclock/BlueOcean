import type { FlexProps } from '@chakra-ui/react';
import { Flex } from '@chakra-ui/react';

export interface NavbarToolbarProps extends FlexProps {}

export function NavbarToolbar(props: FlexProps) {
  const { children, ...rest } = props;
  const menuBg = { base: 'white', _dark: 'navy.800' };
  const shadow = {
    base: '14px 17px 40px 4px rgba(112, 144, 176, 0.18)',
    _dark: '14px 17px 40px 4px rgba(112, 144, 176, 0.06)',
  };
  return (
    <Flex
      ms="auto"
      mt={{ base: '10px', md: 'none' }}
      w={{ base: '100%', md: 'auto' }}
      alignItems="center"
      flexDirection="row"
      bg={menuBg}
      flexWrap="nowrap"
      p="10px"
      borderRadius="30px"
      boxShadow={shadow}
      {...rest}
    >
      {children}
    </Flex>
  );
}
