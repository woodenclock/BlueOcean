import { Menu, Flex, Icon, Portal, Text } from '@chakra-ui/react';
import { MdNotificationsNone } from 'react-icons/md';

export function HorizonNavbarNotification() {
  const textColor = { base: 'secondaryGray.900', _dark: 'white' };
  const textColorBrand = { base: 'brand.700', _dark: 'brand.400' };
  const iconColor = { base: 'gray.400', _dark: 'white' };
  const menuBg = { base: 'white', _dark: 'navy.800' };

  const shadow = {
    base: '14px 17px 40px 4px rgba(112, 144, 176, 0.18)',
    _dark: '14px 17px 40px 4px rgba(112, 144, 176, 0.06)',
  };

  return (
    <Menu.Root>
      <Menu.Trigger p="0px" asChild>
        <Icon
          _hover={{ cursor: 'pointer' }}
          p="0px"
          color={iconColor}
          w="18px"
          h="18px"
          mx="11px"
        >
          <MdNotificationsNone />
        </Icon>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content
            boxShadow={shadow}
            p="20px"
            borderRadius="20px"
            bg={menuBg}
            border="none"
            mt="22px"
            me={{ base: '30px', md: 'unset' }}
            minW={{ base: 'unset', md: '400px', xl: '450px' }}
            maxW={{ base: '360px', md: 'unset' }}
          >
            <Flex w="100%" mb="20px">
              <Text fontSize="md" fontWeight="600" color={textColor}>
                Notifications
              </Text>
              <Text
                fontSize="sm"
                fontWeight="500"
                color={textColorBrand}
                ms="auto"
                cursor="pointer"
              >
                Mark all read
              </Text>
            </Flex>
            <Flex flexDirection="column">
              <Menu.Item
                value="hui-dashboard-pro"
                _hover={{ bg: 'none' }}
                _focus={{ bg: 'none' }}
                px="0"
                borderRadius="8px"
                mb="10px"
              >
                {/*<ItemContent info='Horizon UI Dashboard PRO' />*/}
                Horizon UI Dashboard PRO
              </Menu.Item>
              <Menu.Item
                value="hui-design-sys-free"
                _hover={{ bg: 'none' }}
                _focus={{ bg: 'none' }}
                px="0"
                borderRadius="8px"
                mb="10px"
              >
                {/*<ItemContent info='Horizon Design System Free' />*/}
                Horizon Design System Free
              </Menu.Item>
            </Flex>
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
}
