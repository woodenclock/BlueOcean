import { createContext, useContext } from 'react';
import type { RoutesType } from '@/types';

export interface UseSidebarProps {
  routes: RoutesType[];
  /** When true the sidebar renders as a narrow icon-only rail (labels hidden). */
  collapsed?: boolean;
}

export function useSidebar(props: UseSidebarProps) {
  const { routes, collapsed = false } = props;
  return { routes, collapsed };
}

export type UseSidebarReturn = ReturnType<typeof useSidebar>;

export const SidebarContext = createContext<UseSidebarReturn | undefined>(
  undefined,
);

const useSidebarContext = () => {
  const horizonSidebarContext = useContext(SidebarContext);
  if (horizonSidebarContext === undefined) {
    throw new Error(
      'useSidebarContext must be inside a SidebarContext.Provider',
    );
  }
  return horizonSidebarContext;
};

export function useSidebarItems() {
  const { routes, collapsed } = useSidebarContext();
  return {
    routes,
    collapsed,
  };
}
