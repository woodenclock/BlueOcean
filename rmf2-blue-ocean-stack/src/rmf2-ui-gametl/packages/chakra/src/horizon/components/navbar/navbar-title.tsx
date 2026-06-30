import type { LinkProps } from '@chakra-ui/react';
import { Link } from '@chakra-ui/react';
import { useNavbarTitle } from './use-navbar';

export interface NavbarTitleProps extends LinkProps {}

export function NavbarTitle(props: LinkProps) {
  const { children, ...rest } = props;
  const { routeName } = useNavbarTitle();

  const mainText = { base: 'navy.700', _dark: 'white' };
  return (
    <Link
      color={mainText}
      href="#"
      bg="inherit"
      borderRadius="inherit"
      fontWeight="bold"
      fontSize="34px"
      _hover={{ color: { base: 'navy.700', _dark: 'white' } }}
      _active={{
        bg: 'inherit',
        transform: 'none',
        borderColor: 'transparent',
      }}
      _focus={{
        boxShadow: 'none',
      }}
      {...rest}
    >
      {children ? children : routeName ? routeName : '??'}
    </Link>
  );
}
