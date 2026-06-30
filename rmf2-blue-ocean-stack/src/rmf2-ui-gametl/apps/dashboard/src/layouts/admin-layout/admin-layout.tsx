import { useState } from 'react';
import { Outlet, useNavigation } from 'react-router';
import { Box, Button } from '@chakra-ui/react';
import { MdChevronLeft, MdChevronRight } from 'react-icons/md';
import { Horizon } from '@rmf2-ui/chakra';
import { RMF2IndustrialLogo } from '@/components/icons';
import { Pending } from '@/components/pending';
import { SidebarPartnerLogo } from '@/components/sidebar/sidebar-partner-logo';
import { ColorModeButton } from '@/components/ui/color-mode';
import { routes } from './admin-routes';
import { AdminAvatarMenu } from './admin-avatar-menu';

import Sidebar = Horizon.Sidebar;
import Navbar = Horizon.Navbar;
import Searchbar = Horizon.Searchbar;

// Fixed-sidebar widths (xl+ only). Collapsed = icon-only rail.
const SIDEBAR_W = '300px';
const SIDEBAR_COLLAPSED_W = '90px';

// Custom Chakra theme
export function AdminLayout() {
  const logoColor = { base: 'navy.700', _dark: 'white' };

  const navigation = useNavigation();
  const isNavigating = Boolean(navigation.location);

  // Collapse the fixed sidebar to an icon rail so the content (e.g. the map)
  // gets more room. Toggle lives in the sidebar footer; xl-only.
  const [collapsed, setCollapsed] = useState(false);
  const railW = collapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_W;
  const contentW = `calc(100% - ${railW})`;

  return (
    <Box h="100vh">
      <Sidebar.Root routes={routes} collapsed={collapsed}>
        <Sidebar.Positioner w={railW} transition="width 0.2s ease">
          <Sidebar.Header px={collapsed ? '0' : undefined}>
            <RMF2IndustrialLogo collapsed={collapsed} color={logoColor} />
          </Sidebar.Header>
          <Sidebar.Content>
            <Sidebar.Items />
          </Sidebar.Content>
          <Sidebar.Footer mt="auto" mb="24px" px={4}>
            <SidebarPartnerLogo collapsed={collapsed} />
            <Button
              w="100%"
              colorPalette="blue"
              variant="solid"
              onClick={() => setCollapsed((v) => !v)}
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <MdChevronRight /> : <MdChevronLeft />}
            </Button>
          </Sidebar.Footer>
        </Sidebar.Positioner>

        <Box
          float="right"
          minHeight="100vh"
          height="100%"
          overflow="auto"
          position="relative"
          maxHeight="100%"
          w={{ base: '100%', xl: contentW }}
          maxWidth={{ base: '100%', xl: contentW }}
          transition="all 0.33s cubic-bezier(0.685, 0.0473, 0.346, 1)"
          transitionDuration=".2s, .2s, .35s"
          transitionProperty="top, bottom, width"
          transitionTimingFunction="linear, linear, ease"
        >
          <Navbar.Root routes={routes} zIndex="10">
            <Navbar.Header>
              <Navbar.Breadcrumb />
              <Navbar.Title />
            </Navbar.Header>
            <Navbar.Toolbar>
              {/* Searchbar */}
              <Searchbar />

              {/* Floating Sidebar */}
              <Sidebar.Responsive>
                <Sidebar.Header>
                  <RMF2IndustrialLogo color={logoColor} />
                </Sidebar.Header>
                <Sidebar.Content>
                  <Sidebar.Items />
                </Sidebar.Content>
                <Sidebar.Footer mt="auto" mb="24px" px={4}>
                  <SidebarPartnerLogo />
                </Sidebar.Footer>
              </Sidebar.Responsive>

              {/* Horizon Notification Button */}
              {/*<Horizon.HorizonNavbarNotification /> */}

              {/* Horizon Info Button */}
              {/*<Horizon.HorizonNavbarInfo />*/}

              {/* Color Mode Button */}
              <ColorModeButton
                h="10px"
                w="10px"
                p="0px"
                me="10px"
                color={{ base: 'gray.400', _dark: 'white' }}
              />

              {/* Avatar Button */}
              <AdminAvatarMenu />
            </Navbar.Toolbar>
          </Navbar.Root>

          <Box
            mx="auto"
            p="30px"
            minH="100vh"
            pt={{ base: '180px', md: '120px' }}
          >
            <Outlet />
            {isNavigating && (
              <Pending.Root>
                <Pending.Overlay />
                <Pending.Spinner />
              </Pending.Root>
            )}
          </Box>
        </Box>
      </Sidebar.Root>
    </Box>
  );
}

export default AdminLayout;
