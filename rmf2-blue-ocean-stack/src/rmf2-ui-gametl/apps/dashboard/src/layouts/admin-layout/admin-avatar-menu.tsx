import { Avatar, Flex, Menu, Portal, Text } from '@chakra-ui/react';

export function AdminAvatarMenu() {
  const menuBg = { base: 'white', _dark: 'navy.800' };
  const shadow = {
    base: '14px 17px 40px 4px rgba(112, 144, 176, 0.18)',
    _dark: '14px 17px 40px 4px rgba(112, 144, 176, 0.06)',
  };
  const borderColor = { base: '#E6ECFA', _dark: 'rgba(135, 140, 189, 0.3)' };
  const textColor = { base: 'secondaryGray.900', _dark: 'white' };
  return (
    <Menu.Root>
      <Menu.Trigger>
        <Avatar.Root
          _hover={{ cursor: 'pointer' }}
          color="white"
          bg="#11047A"
          size="sm"
          w="40px"
          h="40px"
        >
          <Avatar.Fallback name="Adela Parkson" />
        </Avatar.Root>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content
            boxShadow={shadow}
            p="0px"
            mt="10px"
            borderRadius="20px"
            bg={menuBg}
            border="none"
          >
            <Flex w="100%" mb="0px">
              <Text
                ps="20px"
                pt="16px"
                pb="10px"
                w="100%"
                borderBottom="1px solid"
                borderColor={borderColor}
                fontSize="sm"
                fontWeight="700"
                color={textColor}
              >
                👋&nbsp; Hey, Adela
              </Text>
            </Flex>
            <Flex flexDirection="column" p="10px">
              <Menu.Item
                value="profile-settings"
                _hover={{ bg: 'none' }}
                _focus={{ bg: 'none' }}
                borderRadius="8px"
                px="14px"
              >
                <Text fontSize="sm">Profile Settings</Text>
              </Menu.Item>
              <Menu.Item
                value="newsletter-settings"
                _hover={{ bg: 'none' }}
                _focus={{ bg: 'none' }}
                borderRadius="8px"
                px="14px"
              >
                <Text fontSize="sm">Newsletter Settings</Text>
              </Menu.Item>
              <Menu.Item
                value="logout"
                _hover={{ bg: 'none' }}
                _focus={{ bg: 'none' }}
                color="red.400"
                borderRadius="8px"
                px="14px"
              >
                <Text fontSize="sm">Log out</Text>
              </Menu.Item>
            </Flex>
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
}
