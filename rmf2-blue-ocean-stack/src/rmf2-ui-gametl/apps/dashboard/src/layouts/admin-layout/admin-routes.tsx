import { Icon } from '@chakra-ui/react';
import {
  MdDashboard,
  MdEventNote,
  MdHome,
  MdMap,
  MdMenuBook,
  MdSmartToy,
} from 'react-icons/md';
import { FaNetworkWired } from 'react-icons/fa';
import { SiUnrealengine } from 'react-icons/si';
import { GrSchedules } from 'react-icons/gr';

import type { RoutesType } from '@rmf2-ui/chakra';

/** Dashboard sidebar/home metadata beyond shared {@link RoutesType}. */
export type DashboardRoute = RoutesType & {
  description?: string;
  children?: DashboardRoute[];
};

export const routes: DashboardRoute[] = [
  {
    name: 'Home',
    path: '/home',
    icon: <Icon as={MdHome} width="20px" height="20px" color="inherit" />,
  },
  {
    name: 'Manual Wiki',
    href: 'https://dev.rmf-industrial.org/latest/',
    description:
      'RMF Industrial documentation — architecture, modules, and getting started.',
    icon: <Icon as={MdMenuBook} width="20px" height="20px" color="inherit" />,
  },
  {
    name: 'System',
    icon: <Icon as={MdDashboard} width="20px" height="20px" color="inherit" />,
    children: [
      {
        name: 'Network',
        path: '/system/network',
        description:
          'Start and check brokers, databases, Redis, and related middleware status.',
        icon: (
          <Icon
            as={FaNetworkWired}
            width="20px"
            height="30px"
            color="inherit"
          />
        ),
      },
      {
        name: 'Simulation',
        icon: (
          <Icon
            as={SiUnrealengine}
            width="20px"
            height="30px"
            color="inherit"
          />
        ),
        path: '/system/simulation',
        description:
          'Onboard devices and services, run UE5 simulation via the Python launcher API.',
      },
      {
        name: 'Map',
        path: '/system/map',
        icon: <Icon as={MdMap} width="20px" height="30px" color="inherit" />,
      },
      {
        name: 'VDA Visualiser',
        path: '/system/vda-visualiser',
        description:
          'Live robot positions, map nodes and edges from the VDA5050 master.',
        icon: (
          <Icon as={MdSmartToy} width="20px" height="30px" color="inherit" />
        ),
      },
    ],
  },
  {
    name: 'Operation',
    icon: <Icon as={MdEventNote} width="20px" height="20px" color="inherit" />,
    children: [
      {
        name: 'Schedule',
        path: '/operation/schedule',
        description:
          'Plan and review operation schedules with Gantt-style timelines.',
        icon: (
          <Icon as={GrSchedules} width="20px" height="30px" color="inherit" />
        ),
      },
    ],
  },
];

export default routes;
