export interface Task {
  id: string;
  type: string;
  description?: string;
  startTime: Date;
  endTime?: Date;
  seriesId?: string;
  processId?: string;
  resourceId?: string;
  deadline?: Date;
  status: string;
  plannedStartTime?: Date;
  plannedEndTime?: Date;
  // estimatedDuration?: number
  actualStartTime?: Date;
  actualEndTime?: Date;
  taskDetails: any; // eslint-disable-line @typescript-eslint/no-explicit-any
}
