import { useRef } from 'react';
import type { FlexProps } from '@chakra-ui/react';
import {
  CloseButton,
  Flex,
  Drawer,
  Icon,
  useDisclosure,
  Portal,
} from '@chakra-ui/react';
import { IoMenuOutline } from 'react-icons/io5';

export interface SidebarResponsiveProps extends FlexProps {}

export function SidebarResponsive(props: SidebarResponsiveProps) {
  const sidebarBackgroundColor = { base: 'white', _dark: 'navy.800' };
  const menuColor = { base: 'gray.400', _dark: 'white' };
  const { open, setOpen } = useDisclosure();
  const btnRef = useRef<HTMLInputElement | null>(null);

  const { children, ...rest } = props;

  return (
    <Flex display={{ base: 'flex', xl: 'none' }} alignItems="center" {...rest}>
      <Flex
        ref={btnRef}
        w="max-content"
        h="max-content"
        onClick={() => setOpen(true)}
      >
        <Icon
          color={menuColor}
          my="auto"
          w="20px"
          h="20px"
          mx="10px"
          _hover={{ cursor: 'pointer' }}
        >
          <IoMenuOutline />
        </Icon>
      </Flex>
      <Drawer.Root
        open={open}
        onOpenChange={(e) => setOpen(e.open)}
        placement={document.documentElement.dir === 'rtl' ? 'end' : 'start'}
        finalFocusEl={() => btnRef.current}
      >
        <Portal>
          <Drawer.Backdrop />
          <Drawer.Positioner>
            <Drawer.Content w="285px" maxW="285px" bg={sidebarBackgroundColor}>
              <Drawer.CloseTrigger asChild>
                <CloseButton
                  zIndex="3"
                  _focus={{ boxShadow: 'none' }}
                  _hover={{ boxShadow: 'none' }}
                />
              </Drawer.CloseTrigger>
              <Drawer.Body maxW="285px" px="0rem" pb="0">
                {children}
              </Drawer.Body>
            </Drawer.Content>
          </Drawer.Positioner>
        </Portal>
      </Drawer.Root>
    </Flex>
  );
}

export default SidebarResponsive;
