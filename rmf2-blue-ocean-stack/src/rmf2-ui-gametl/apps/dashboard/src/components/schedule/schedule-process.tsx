import { ComponentProps, FormEvent, useEffect } from 'react';
import type { BoxProps } from '@chakra-ui/react';
import {
  Box,
  Button,
  Flex,
  Field,
  Combobox,
  Portal,
  useComboboxContext,
  useFilter,
  useListCollection,
} from '@chakra-ui/react';
import { useTheme } from 'next-themes';
import { useScheduleProcess } from './use-schedule';
import {
  ReactFlow,
  Background,
  Controls,
  Node,
  Edge,
  MarkerType,
  Panel,
  Position,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import Dagre from '@dagrejs/dagre';
import type { RTS } from '@rmf2-ui/data';

const getLayoutElements = (
  nodes: Node[],
  edges: Edge[],
  direction: string = 'LR',
) => {
  const defaultNodeWidth = 172;
  const defaultNodeHeight = 36;
  const isHorizontal = direction === 'LR';
  const dagreGraph = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction });
  edges.forEach((edge) => dagreGraph.setEdge(edge.source, edge.target));
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: node.measured?.width ?? defaultNodeWidth,
      height: node.measured?.height ?? defaultNodeHeight,
    });
  });

  Dagre.layout(dagreGraph);

  const newNodes: Node[] = nodes.map((node) => {
    const dagreNode = dagreGraph.node(node.id);
    const x = dagreNode.x - (node.measured?.width ?? defaultNodeWidth) / 2;
    const y = dagreNode.y - (node.measured?.height ?? defaultNodeHeight) / 2;
    const newNode = {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      // We are shifting the dagre node position (anchor=center center) to the top left
      // so it matches the React Flow node anchor point (top left).
      position: { x, y },
    };

    // override type
    const dependants = dagreGraph.inEdges(node.id) ?? [];
    const successors = dagreGraph.outEdges(node.id) ?? [];
    if (successors.length === 0) {
      newNode.type = 'output';
    }

    if (dependants.length === 0) {
      newNode.type = 'input';
    }

    return newNode;
  });

  return {
    nodes: newNodes,
    edges,
  };
};

function ComboboxHiddenInput(props: ComponentProps<'input'>) {
  const combobox = useComboboxContext();
  return <input type="hidden" value={combobox.value[0]} readOnly {...props} />;
}

export interface ScheduleProcessProps extends BoxProps {}

export function ScheduleProcess(props: ScheduleProcessProps) {
  const { ...rest } = props;
  const { schedule, viewProcess, setViewProcess } = useScheduleProcess();
  const { contains } = useFilter({ sensitivity: 'base' });
  const {
    collection,
    filter,
    set: setCollection,
  } = useListCollection<string>({
    initialItems: ['test-item1', 'test-item2'],
    filter: contains,
  });
  const nodeDefaults = {}; // unused
  const { resolvedTheme, forcedTheme } = useTheme();
  const colorMode = (forcedTheme || resolvedTheme) as 'light' | 'dark';

  useEffect(() => {
    if (schedule === undefined) {
      return;
    }

    if (schedule.processes.length === 0) {
      return;
    }

    setCollection(schedule.processes.map((value) => value.id));

    const process: RTS.Process = viewProcess ?? schedule.processes[0];

    const taskMap: Record<string, RTS.Task> = {};
    for (const task of schedule.tasks) {
      taskMap[task.id] = task;
    }

    const nodes: Node[] = process.graph.map((element) => ({
      id: element.id,
      position: { x: 0, y: 0 },
      data: { label: taskMap[element.id].description },
      ...nodeDefaults,
    }));

    const edges: Edge[] = [];

    for (const element of process.graph) {
      element.needs.forEach((dependency) => {
        edges.push({
          id: `${dependency.id}->${element.id}`,
          type: 'bezier',
          source: dependency.id,
          target: element.id,
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        });
      });
    }

    const { nodes: layoutNodes, edges: layoutEdges } = getLayoutElements(
      nodes,
      edges,
    );
    setNodes(layoutNodes);
    setEdges(layoutEdges);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schedule, viewProcess]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (schedule === undefined) {
      return;
    }

    const formData = new FormData(event.currentTarget);
    const viewProcessId = formData.get('viewProcessId');
    if (viewProcessId !== null) {
      const newViewProcess = schedule.processes.find(
        (value) => value.id === viewProcessId,
      );
      setViewProcess(newViewProcess);
    }
  };

  return (
    <Box w="100%" h="600px" {...rest}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        colorMode={colorMode}
      >
        <Panel>
          <form onSubmit={handleSubmit}>
            <Field.Root>
              <Field.Label>Process ID</Field.Label>
              <Flex alignItems="center" gap="10px">
                <Combobox.Root
                  collection={collection}
                  onInputValueChange={(e) => filter(e.inputValue)}
                  w="350px"
                >
                  <Combobox.Control>
                    <Combobox.Input placeholder="Type to search" />
                    <Combobox.IndicatorGroup>
                      <Combobox.ClearTrigger />
                      <Combobox.Trigger />
                    </Combobox.IndicatorGroup>
                  </Combobox.Control>
                  <ComboboxHiddenInput name="viewProcessId" />
                  <Portal>
                    <Combobox.Positioner>
                      <Combobox.Content>
                        <Combobox.Empty>No items found</Combobox.Empty>
                        {collection.items.map((item) => (
                          <Combobox.Item item={item} key={item}>
                            {item}
                            <Combobox.ItemIndicator />
                          </Combobox.Item>
                        ))}
                      </Combobox.Content>
                    </Combobox.Positioner>
                  </Portal>
                </Combobox.Root>
                <Button size="sm" type="submit">
                  Update
                </Button>
              </Flex>
            </Field.Root>
          </form>
        </Panel>
        <Background />
        <Controls />
      </ReactFlow>
    </Box>
  );
}
