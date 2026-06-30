import type { Task } from './task';
import type { Process } from './process';

export interface Schedule {
  tasks: Task[];
  processes: Process[];
}
