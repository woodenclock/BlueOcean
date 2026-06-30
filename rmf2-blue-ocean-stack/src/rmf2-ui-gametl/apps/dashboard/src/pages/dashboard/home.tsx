import { NavLink } from 'react-router';
import { Box, SimpleGrid, Stack, Text } from '@chakra-ui/react';
import {
  routes as dashboardRoutes,
  type DashboardRoute,
} from '@/layouts/admin-layout/admin-routes';

type NavigableRoute = DashboardRoute & { path?: string; href?: string };

function leafGridRoutes(allRoutes: DashboardRoute[]): NavigableRoute[] {
  const out: NavigableRoute[] = [];
  for (const route of allRoutes) {
    if (route.path === '/home') continue;
    if (route.children?.length) {
      for (const child of route.children) {
        if (child.path != null || child.href != null) out.push(child);
      }
    } else if (route.path != null || route.href != null) {
      out.push(route);
    }
  }
  return out;
}

function routeCardKey(route: NavigableRoute): string {
  return route.path ?? route.href ?? route.name;
}

export function Home() {
  const destinations = leafGridRoutes(dashboardRoutes);
  const cardBg = { base: 'secondaryGray.300', _dark: 'whiteAlpha.100' };
  const borderColor = { base: 'gray.200', _dark: 'whiteAlpha.200' };
  const titleColor = { base: 'secondaryGray.900', _dark: 'white' };
  const descColor = 'secondaryGray.600';

  return (
    <Stack gap={{ base: 8, md: 10 }} align="center" py={{ base: 4, md: 8 }}>
      <Stack gap={2} textAlign="center" maxW="lg" px={2}>
        <Text fontSize="2xl" fontWeight="bold" color={titleColor}>
          RMF2
        </Text>
        <Text color={descColor} fontSize="md">
          Choose an area to open tools that match the sidebar.
        </Text>
      </Stack>

      <SimpleGrid
        columns={{ base: 1, sm: 2, lg: 3 }}
        gap={6}
        w="full"
        maxW="5xl"
      >
        {destinations.map((route) => {
          const card = (
            <Box
              h="full"
              borderWidth="1px"
              borderColor={borderColor}
              bg={cardBg}
              borderRadius="xl"
              p={6}
              transitionProperty="transform, box-shadow"
              transitionDuration="0.15s"
              transitionTimingFunction="ease"
              _hover={{
                transform: 'translateY(-2px)',
                shadow: 'md',
              }}
              _active={{
                transform: 'translateY(0) scale(0.99)',
                shadow: 'sm',
              }}
            >
              <Stack gap={4} align="flex-start">
                <Box
                  color={{ base: 'brand.500', _dark: 'brand.300' }}
                  lineHeight={1}
                  transform="scale(1.55)"
                  transformOrigin="left center"
                  aria-hidden
                >
                  {route.icon}
                </Box>
                <Stack gap={1} align="flex-start">
                  <Text fontWeight="bold" fontSize="lg" color={titleColor}>
                    {route.name}
                  </Text>
                  <Text fontSize="sm" color={descColor}>
                    {route.description ?? 'Open this section.'}
                  </Text>
                </Stack>
              </Stack>
            </Box>
          );

          if (route.href) {
            return (
              <a
                key={routeCardKey(route)}
                href={route.href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  textDecoration: 'none',
                  width: '100%',
                  height: '100%',
                  display: 'inline-block',
                }}
              >
                {card}
              </a>
            );
          }

          return (
            <NavLink
              key={routeCardKey(route)}
              to={route.path!}
              style={{ textDecoration: 'none', width: '100%', height: '100%' }}
            >
              {card}
            </NavLink>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}
