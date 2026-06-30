import { useCallback, useEffect, useRef } from 'react';
import { chakra } from '@chakra-ui/react';
import { useScheduleGantt } from './use-schedule';
import { DataSet } from 'vis-data/esnext';
import type { DataItem, DataGroup } from 'vis-timeline/esnext';
import { Timeline } from 'vis-timeline/esnext';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import './vis-timeline-styles.css';

const COLOR_CLASSES = ['green', 'magenta', 'yellow', 'orange'];
const OPTIONS = { height: '680px', orientation: 'top', zoomFriction: 0 };
const DEFAULT_ZOOM_LEVEL = 30 * 60; // Default to zoom 30min

interface VisTimelineContext {
  dataGroups: DataSet<DataGroup>;
  dataItems: DataSet<DataItem>;
  timeline: Timeline;
}

export function ScheduleGantt() {
  const { tasks, openTaskViewDialog } = useScheduleGantt();
  const visTimelineContext = useRef<VisTimelineContext>(null);

  const containerRef = useCallback((node: HTMLDivElement) => {
    if (visTimelineContext.current !== null) {
      return;
    }

    if (node !== null) {
      // GENERATE NEW TIMELINE
      const dataGroups: DataSet<DataGroup> = new DataSet();
      const dataItems: DataSet<DataItem> = new DataSet();
      node.innerHTML = '';
      visTimelineContext.current = {
        dataGroups,
        dataItems,
        timeline: new Timeline(node, dataItems, dataGroups, {
          ...OPTIONS,
          start: new Date(Date.now() - (DEFAULT_ZOOM_LEVEL / 2) * 1000),
          end: new Date(Date.now() + (DEFAULT_ZOOM_LEVEL / 2) * 1000),
        }),
      };
    }
  }, []);

  // Update timeline on tasks changes
  useEffect(() => {
    if (!visTimelineContext.current) {
      return;
    }

    const filteredTasks = tasks.filter(
      (task) =>
        task?.type !== 'ihi/dummy' && task?.type !== 'ihi/warehouse_task',
    );

    const groupIds = new Set<string>();
    const taskIds = new Set<string>();
    const taskTypes = new Set<string>();
    for (const task of filteredTasks) {
      taskTypes.add(task.type);
      groupIds.add(task.resourceId ?? 'unassigned');
      taskIds.add(task.id);
    }

    // Prep color map
    const colorMap: Record<string, string> = {};
    Array.from(taskTypes).reduce((colorMap, taskType, index) => {
      const colorIndex = index % COLOR_CLASSES.length;
      colorMap[taskType] = COLOR_CLASSES[colorIndex];
      return colorMap;
    }, colorMap);

    // Prep group map
    const sortedGroupIds = Array.from(groupIds).sort();
    const groupMap: Record<string, number> = {};
    sortedGroupIds.reduce((groupMap, groupId, index) => {
      groupMap[groupId] = index;
      return groupMap;
    }, groupMap);

    // Prep data for visualisation
    const newDataGroups: DataGroup[] = sortedGroupIds.map((groupId, index) => {
      return {
        id: index,
        content: groupId,
      };
    });
    const newDataItems: DataItem[] = filteredTasks.map((task) => ({
      id: task.id,
      content: task.description ?? '',
      start: task.startTime,
      end: task.endTime ?? new Date(task.startTime.getTime() + 20 * 1000),
      className: colorMap[task.type], // change colors in COLOR_CLASSES
      group: groupMap[task.resourceId ?? 'unassigned'],
      title: `${task?.resourceId} \n@ ${task?.taskDetails?.resource_zone} zone`,
    }));

    // update data
    visTimelineContext.current.dataGroups.update(newDataGroups);
    visTimelineContext.current.dataItems.update(newDataItems);

    // remove deleted data
    const deletedDataItems = visTimelineContext.current.dataItems
      .getIds()
      .reduce((acc: (number | string)[], cur) => {
        if (typeof cur === 'number') {
          acc.push(cur);
          return acc;
        }
        if (taskIds.has(cur)) {
          return acc;
        }
        acc.push(cur);
        return acc;
      }, []);

    visTimelineContext.current.dataItems.remove(deletedDataItems);
    // // Update window
    // visTimelineContext.current.timeline.setWindow(
    //   new Date(Date.now() - (DEFAULT_ZOOM_LEVEL / 2) * 1000),
    //   new Date(Date.now() + (DEFAULT_ZOOM_LEVEL / 2) * 1000),
    // );

    // TODAY
    const todayButton = document.getElementById('todayId');
    if (!todayButton) {
      return;
    }
    todayButton.addEventListener('click', () => {
      if (!visTimelineContext.current) {
        return;
      }
      const now = new Date();
      visTimelineContext.current.timeline.moveTo(now);
    });

    // DATETIME
    const datetimeInput = document.getElementById('datetimeInputId');
    if (!datetimeInput) {
      return;
    }
    datetimeInput.addEventListener('change', (event) => {
      if (!visTimelineContext.current) {
        return;
      }
      const target = event.target as HTMLInputElement;
      const selectedTime = new Date(target.value);
      visTimelineContext.current.timeline.moveTo(selectedTime);
    });

    // return () => timelineRef.current = null
  }, [tasks]);

  useEffect(() => {
    if (!visTimelineContext.current) {
      return;
    }

    visTimelineContext.current.timeline.on('doubleClick', (properties) => {
      // Open ScheduleViewTask when double click on a timeline item
      if (properties.item !== null) {
        openTaskViewDialog(properties.item);
      }
    });
  }, [openTaskViewDialog]);

  return (
    <chakra.div
      ref={containerRef}
      minHeight="700px"
      maxHeight="900px"
      css={{
        '--vis-text-color': {
          base: 'colors.gray.700',
          _dark: 'colors.white',
        },
        '--vis-label-text-color': {
          base: 'colors.gray.700',
          _dark: 'colors.white',
        },
      }}
    />
  );
}

export default ScheduleGantt;
