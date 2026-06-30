import type { RouteObject } from 'react-router';
import { HomeRedirect } from './home-redirect';
import { NotFoundRedirect } from './not-found-redirect';

export const AdminRoutes: RouteObject[] = [
  {
    // Home
    path: 'home',
    lazy: async () => {
      const { Home } = await import('@/pages/dashboard/home');
      return { Component: Home };
    },
  },
  {
    // System
    path: 'system',
    children: [
      // System Home
      {
        index: true,
        lazy: async () => {
          const { Home } = await import('@/pages/dashboard/home');
          return { Component: Home };
        },
      },
      {
        // Network
        path: 'network',
        lazy: async () => {
          const { Network } = await import('@/pages/dashboard/system/network');
          return { Component: Network };
        },
      },
      {
        // Simulation
        path: 'simulation',
        lazy: async () => {
          const { Simulation } = await import(
            '@/pages/dashboard/system/simulation'
          );
          return { Component: Simulation };
        },
      },
      {
        // Map
        path: 'map',
        lazy: async () => {
          const { Map } = await import('@/pages/dashboard/system/map');
          return { Component: Map };
        },
      },
      {
        // VDA Visualiser
        path: 'vda-visualiser',
        lazy: async () => {
          const { VdaVisualiser } = await import(
            '@/pages/dashboard/system/vda-visualiser'
          );
          return { Component: VdaVisualiser };
        },
      },
    ],
  },
  {
    path: 'operation/schedule',
    lazy: async () => {
      const { Schedule } = await import('@/pages/dashboard/operation/schedule');
      return { Component: Schedule };
    },
  },
];

export const dashboardRoutes: RouteObject[] = [
  {
    // Redirect index page to /home
    index: true,
    Component: HomeRedirect,
  },
  {
    lazy: async () => {
      const { AdminLayout } = await import('@/layouts');
      return { Component: AdminLayout };
    },
    children: AdminRoutes,
  },
  {
    path: '*',
    Component: NotFoundRedirect,
  },
];

export const routes: RouteObject[] = [
  {
    path: '/',
    children: dashboardRoutes,
  },
];

export default routes;
