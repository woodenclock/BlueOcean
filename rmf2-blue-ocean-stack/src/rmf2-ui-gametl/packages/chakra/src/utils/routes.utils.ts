import type { RoutesType } from '@/types';

/** Stable key for accordion sections without a navigable path. */
export function routeSectionKey(route: RoutesType): string {
  return route.path ?? route.name;
}

/** Whether the current URL belongs to this route or any of its children. */
export function routeMatchesLocation(
  route: RoutesType,
  pathname: string,
): boolean {
  const loc = pathname.toLowerCase();
  if (route.children?.length) {
    return route.children.some(
      (child) => child.path != null && loc.startsWith(child.path.toLowerCase()),
    );
  }
  return route.path != null && loc.startsWith(route.path.toLowerCase());
}
