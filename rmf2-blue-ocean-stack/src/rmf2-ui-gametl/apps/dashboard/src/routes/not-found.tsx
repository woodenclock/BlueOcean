import { NavLink } from 'react-router';
import { Box, Button, Stack, Text } from '@chakra-ui/react';

export function NotFound() {
  const titleColor = { base: 'secondaryGray.900', _dark: 'white' };
  const descColor = 'secondaryGray.600';

  return (
    <Stack
      gap={6}
      align="center"
      justify="center"
      minH="60vh"
      py={{ base: 8, md: 12 }}
      px={4}
      textAlign="center"
    >
      <Text fontSize="6xl" fontWeight="bold" color={titleColor} lineHeight={1}>
        404
      </Text>
      <Stack gap={2} maxW="md">
        <Text fontSize="xl" fontWeight="semibold" color={titleColor}>
          Page not found
        </Text>
        <Text color={descColor}>
          The page you are looking for does not exist or has been moved.
        </Text>
      </Stack>
      <Box>
        <NavLink to="/home" style={{ textDecoration: 'none' }}>
          <Button colorPalette="brand">Back to home</Button>
        </NavLink>
      </Box>
    </Stack>
  );
}

export default NotFound;
