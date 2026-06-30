import { Fragment } from 'react';
import type { BoxProps } from '@chakra-ui/react';
import { Breadcrumb, Box, Menu, Portal, Link } from '@chakra-ui/react';
import { useNavbarBreadcrumb } from './use-navbar';

interface RouteComponent {
  name: string;
  path: string;
}

interface NavbarBreadcrumbFullProps extends Breadcrumb.RootProps {
  routeComponents: RouteComponent[];
  baseComponent: RouteComponent;
  textColor?: string | Record<string, string>;
  menuBg?: string | Record<string, string>;
}

function NavbarBreadcrumbFull(props: NavbarBreadcrumbFullProps) {
  const { routeComponents, baseComponent, textColor, ...rest } = props;
  return (
    <Breadcrumb.Root {...rest}>
      <Breadcrumb.List>
        <Breadcrumb.Item color={textColor} fontSize="sm">
          <Breadcrumb.Link href={baseComponent.path} color={textColor}>
            {baseComponent.name}
          </Breadcrumb.Link>
        </Breadcrumb.Item>
        {routeComponents.map((component: RouteComponent, index: number) => (
          <Fragment key={index}>
            <Breadcrumb.Separator />

            <Breadcrumb.Item color={textColor} fontSize="sm">
              <Breadcrumb.Link href={component.path} color={textColor}>
                {component.name}
              </Breadcrumb.Link>
            </Breadcrumb.Item>
          </Fragment>
        ))}
      </Breadcrumb.List>
    </Breadcrumb.Root>
  );
}

interface NavbarBreadcrumbMiniProps extends NavbarBreadcrumbFullProps {}

function NavbarBreadcrumbMini(props: NavbarBreadcrumbMiniProps) {
  const { routeComponents, baseComponent, textColor, menuBg, ...rest } = props;

  const getLastComponent = (): RouteComponent | undefined => {
    if (routeComponents.length < 1) {
      return undefined;
    }

    return routeComponents[routeComponents.length - 1];
  };

  const lastComponent = getLastComponent();

  return (
    <Breadcrumb.Root {...rest}>
      <Breadcrumb.List>
        <Menu.Root>
          <Menu.Trigger asChild>
            <Breadcrumb.Ellipsis _hover={{ cursor: 'pointer' }} />
          </Menu.Trigger>
          <Portal>
            <Menu.Positioner>
              <Menu.Content borderRadius="5px" bg={menuBg} border="none">
                <Menu.Item value="main-dashboard">
                  <Link color={textColor} href={baseComponent.path}>
                    {baseComponent.name}
                  </Link>
                </Menu.Item>
                {routeComponents.map(
                  (component: RouteComponent, index: number) =>
                    index < routeComponents.length - 1 && (
                      <Fragment key={index}>
                        <Menu.Separator />

                        <Menu.Item value={component.name}>
                          <Link href={component.path} color={textColor}>
                            {component.name}
                          </Link>
                        </Menu.Item>
                      </Fragment>
                    ),
                )}
              </Menu.Content>
            </Menu.Positioner>
          </Portal>
        </Menu.Root>
        {lastComponent && (
          <>
            <Breadcrumb.Separator />

            <Breadcrumb.Item color={textColor} fontSize="sm">
              <Breadcrumb.Link href={lastComponent.path} color={textColor}>
                {lastComponent.name}
              </Breadcrumb.Link>
            </Breadcrumb.Item>
          </>
        )}
      </Breadcrumb.List>
    </Breadcrumb.Root>
  );
}

export interface NavbarBreadcrumbProps extends BoxProps {}

export function NavbarBreadcrumb(props: NavbarBreadcrumbProps) {
  const { ...rest } = props;

  const { routeComponents } = useNavbarBreadcrumb();

  const baseRouteComponent: RouteComponent = {
    name: 'RMF2 Dashboard',
    path: '/',
  };

  const textColor = { base: 'gray.700', _dark: 'white' };
  const menuBg = { base: 'white', _dark: 'navy.800' };

  return (
    <Box {...rest}>
      <NavbarBreadcrumbFull
        size="lg"
        display={{ base: 'none', md: 'block' }}
        routeComponents={routeComponents}
        baseComponent={baseRouteComponent}
        textColor={textColor}
      />
      <NavbarBreadcrumbMini
        size="lg"
        display={{ base: 'flex', md: 'none' }}
        routeComponents={routeComponents}
        baseComponent={baseRouteComponent}
        textColor={textColor}
        menuBg={menuBg}
      />
    </Box>
  );
}
