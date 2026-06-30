import { Button, Menu, Icon, Portal, Stack, Link } from '@chakra-ui/react';
import { MdInfoOutline } from 'react-icons/md';

export function HorizonNavbarInfo() {
  const textColor = { base: 'secondaryGray.900', _dark: 'white' };
  const iconColor = { base: 'gray.400', _dark: 'white' };
  const borderButtonColor = {
    base: 'secondaryGray.500',
    _dark: 'whiteAlpha.200',
  };
  const menuBg = { base: 'white', _dark: 'navy.800' };

  const shadow = {
    base: '14px 17px 40px 4px rgba(112, 144, 176, 0.18)',
    _dark: '14px 17px 40px 4px rgba(112, 144, 176, 0.06)',
  };

  return (
    <Menu.Root>
      <Menu.Trigger p="0px">
        <Icon mb="2px" color={iconColor} w="18px" h="18px" mx="10px">
          <MdInfoOutline />
        </Icon>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content
            boxShadow={shadow}
            p="20px"
            me={{ base: '30px', md: 'unset' }}
            borderRadius="20px"
            bg={menuBg}
            mt="22px"
            minW={{ base: 'unset' }}
            maxW={{ base: '360px', md: 'unset' }}
          >
            {/*<Image src={navImage} borderRadius='16px' mb='28px' />*/}
            <Stack>
              <Link w="100%" href="https://horizon-ui.com/pro">
                <Button w="100%" h="44px" variant="brand">
                  Buy Horizon UI PRO
                </Button>
              </Link>
              <Link
                w="100%"
                href="https://horizon-ui.com/documentation/docs/introduction"
              >
                <Button
                  w="100%"
                  h="44px"
                  border="1px solid"
                  bg="transparent"
                  variant="ghost"
                  borderColor={borderButtonColor}
                >
                  See Documentation
                </Button>
              </Link>
              <Link
                w="100%"
                href="https://github.com/horizon-ui/horizon-ui-chakra-ts"
              >
                <Button
                  w="100%"
                  h="44px"
                  variant="outline"
                  color={textColor}
                  bg="transparent"
                >
                  Try Horizon Free
                </Button>
              </Link>
            </Stack>
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
}
