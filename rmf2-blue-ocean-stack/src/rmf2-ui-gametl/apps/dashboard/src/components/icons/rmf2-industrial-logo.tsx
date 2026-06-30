import type { BoxProps } from '@chakra-ui/react';
import { Box, Text } from '@chakra-ui/react';

export interface RMF2IndustrialLogoProps extends BoxProps {
  collapsed?: boolean;
}

export function RMF2IndustrialLogo({
  collapsed = false,
  color = { base: 'navy.700', _dark: 'white' },
  ...rest
}: RMF2IndustrialLogoProps) {
  if (collapsed) {
    return (
      <Box textAlign="center" my="10px" {...rest}>
        <Text fontSize="lg" fontWeight="bold" color={color} lineHeight="1.1">
          RMF
        </Text>
        <Text
          fontSize="sm"
          fontWeight="semibold"
          color={color}
          lineHeight="1.1"
        >
          2
        </Text>
      </Box>
    );
  }

  return (
    <Box textAlign="center" my="10px" {...rest}>
      <Text
        fontSize="5xl"
        fontWeight="bold"
        letterSpacing="tight"
        color={color}
        lineHeight="1"
      >
        RMF2
      </Text>
      <Text fontSize="lg" fontWeight="semibold" color={color} mt="4px">
        industrial
      </Text>
    </Box>
  );
}

export default RMF2IndustrialLogo;
