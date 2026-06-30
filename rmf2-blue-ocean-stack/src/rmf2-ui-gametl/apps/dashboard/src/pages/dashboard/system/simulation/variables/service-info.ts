type RowObj = {
  name: string;
  status: string;
  type: string;
};

export const serviceInfo: RowObj[] = [
  {
    name: 'RMF2.0 Task Orchestrator',
    status: 'Online',
    type: 'General Task Execution Service',
  },
  {
    name: 'IHI Task Scheduler',
    status: 'Online',
    type: 'General Scheduling Service',
  },
  {
    name: 'RMF2.0 Multi Agent Path Finder',
    status: 'Online',
    type: 'Mobile Robot Planning Service',
  },
  {
    name: 'RMF2.0 VDA5050 Executor',
    status: 'Online',
    type: 'Mobile Robot Execution Service',
  },
];
