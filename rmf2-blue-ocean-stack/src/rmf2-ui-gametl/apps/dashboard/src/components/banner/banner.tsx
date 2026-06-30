import type {
  TextProps,
  BoxProps,
  ButtonProps,
  FlexProps,
} from '@chakra-ui/react';
import { Text, Box, Button, Flex } from '@chakra-ui/react';

export interface BannerRootProps extends BoxProps {
  colorPalette?: string;
}

export function BannerRoot(props: BannerRootProps) {
  const { children, colorPalette, ...rest } = props;

  const gradientColor: string = colorPalette ? colorPalette : 'horizonTeal';

  return (
    <Box
      direction="row"
      bgGradient="to-r"
      gradientFrom={gradientColor + '.600'}
      gradientTo={gradientColor + '.100'}
      borderRadius="14px"
      py={{ base: '30px', md: '56px' }}
      px={{ base: '30px', md: '64px' }}
      w="100%"
      {...rest}
    >
      {children}
    </Box>
  );
}

export interface BannerHeaderProps extends TextProps {}

export function BannerHeader(props: BannerHeaderProps) {
  const { children, ...rest } = props;
  return (
    <Text
      fontSize={{ base: '30px', md: '44px' }}
      color="white"
      mb="14px"
      fontWeight="700"
      lineHeight={{ base: '32px', md: '42px' }}
      {...rest}
    >
      {children}
    </Text>
  );
}

export interface BannerContentProps extends FlexProps {}

export function BannerContent(props: BannerContentProps) {
  const { children, ...rest } = props;
  return (
    <Flex
      align={{ base: 'start', md: 'center' }}
      flexDirection={{ base: 'column', md: 'row' }}
      gap={{ base: '10px', md: '20px' }}
      {...rest}
    >
      {children}
    </Flex>
  );
}

export interface BannerButtonProps extends ButtonProps {}

export function BannerButton(props: BannerButtonProps) {
  const { children, ...rest } = props;

  return (
    <Button
      bg="orange.400"
      color="black"
      _hover={{ bg: 'whiteAlpha.900' }}
      _active={{ bg: 'blue.200' }}
      _focus={{ bg: 'white' }}
      fontWeight="500"
      fontSize={{ base: '20px', md: '28px' }}
      py="20px"
      w={{ base: '250px', md: '300px' }}
      borderRadius="5px"
      {...rest}
    >
      {children}
    </Button>
  );
}
