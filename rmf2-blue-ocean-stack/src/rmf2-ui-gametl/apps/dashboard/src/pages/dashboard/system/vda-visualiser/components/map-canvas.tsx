// SVG render of the master map: a master-frame map image backdrop, edges, nodes
// (click = set goal), robots (click = arm), and a planner-frame axis overlay.
// Mouse wheel zooms, click-drag pans; default view fits all nodes.
import { useEffect, useRef, useState } from 'react';
import { Box, Button, HStack, IconButton, Text } from '@chakra-ui/react';

import { RotateCcwIcon } from './rotate-ccw-icon';

import {
  buildAdjacency,
  logicalGraphNode,
  shortestPath,
  snapToNode,
} from '../graph';
import { toSchedulerId } from '../scheduler-api';
import type {
  AgvState,
  MapData,
  MapImageMeta,
  RackMap,
  RobotGoal,
  SchedulerRobotId,
} from '../types';
import {
  GOAL_GOLD,
  ROBOT_COLOR_BY_ID,
  robotColor,
  robotStyle,
  SELECTED_COLOR,
  TEXT_SHADOW,
  VISUAL,
} from './constants';
import {
  axisArrowHead,
  boundsFromPoints,
  computeProjection,
  expandBounds,
  imageTransform,
  mapImageBoundsPx,
  type BoundsPx,
} from './projection';
import { Tooltip } from '@/components/ui/tooltip';
import { ToggleTip } from '@/components/ui/toggle-tip';

// Zoom clamps (× the node-fit view) and the drag distance past which a press is
// treated as a pan, not a click. MIN_ZOOM = 0.5 allows zooming out to 50% so
// the full map image (which can extend beyond the node bounds) stays visible.
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 12;
const ZOOM_PRESETS = [50, 75, 100, 125, 150] as const;
const DRAG_THRESHOLD = 4;
const FIT_PADDING = 0.2;

type FitMode = 'map' | 'robots' | 'nodes';
const FIT_MODES: FitMode[] = ['map', 'robots', 'nodes'];
const FIT_MODE_LABEL: Record<FitMode, string> = {
  map: 'Fit Map',
  robots: 'Fit Robots',
  nodes: 'Fit Nodes',
};

interface MapCanvasProps {
  map: MapData | null;
  agvs: AgvState[];
  rotated: boolean;
  onToggleRotate?: () => void;
  mapImage: MapImageMeta | null;
  goals: Partial<Record<SchedulerRobotId, RobotGoal>>;
  racks: RackMap;
  selectedRobot: SchedulerRobotId | null;
  onSelectRobot: (id: SchedulerRobotId) => void;
  onPickNode: (nodeId: string) => void;
}

export function MapCanvas({
  map,
  agvs,
  rotated,
  onToggleRotate,
  mapImage,
  goals,
  racks,
  selectedRobot,
  onSelectRobot,
  onPickNode,
}: MapCanvasProps) {
  const nodes = map?.nodes ?? [];
  const nodeById = new Map(nodes.map((n) => [n.node_id, n]));

  const { svgW, svgH, toPx, robotDeg, axis } = computeProjection(
    nodes,
    rotated,
  );

  // Viewport (SVG viewBox). Default = the node-fit box {0,0,svgW,svgH}; wheel
  // zooms (shrinks w/h about the cursor), drag pans (shifts x/y). w:h stays at
  // svgW:svgH so the element keeps a stable aspect ratio.
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState({ x: 0, y: 0, w: svgW, h: svgH });
  const viewRef = useRef(view);
  viewRef.current = view;
  const suppressClickRef = useRef(false);
  const [grabbing, setGrabbing] = useState(false);
  const [zoomTipOpen, setZoomTipOpen] = useState(false);
  const zoomTipPinnedRef = useRef(false);
  const [fitModeIndex, setFitModeIndex] = useState(() =>
    FIT_MODES.indexOf('nodes'),
  );

  const clampViewWidth = (w: number) =>
    Math.min(Math.max(w, svgW / MAX_ZOOM), svgW / MIN_ZOOM);

  const setZoomAboutCenter = (targetPct: number) => {
    const minPct = MIN_ZOOM * 100;
    const maxPct = MAX_ZOOM * 100;
    const pct = Math.min(Math.max(targetPct, minPct), maxPct);
    const { x, y, w, h } = viewRef.current;
    const cx = x + w / 2;
    const cy = y + h / 2;
    const newW = clampViewWidth(svgW / (pct / 100));
    const newH = h * (newW / w);
    setView({ x: cx - newW / 2, y: cy - newH / 2, w: newW, h: newH });
  };

  const stepZoom = (direction: -1 | 1) => {
    const current = Math.round((svgW / viewRef.current.w) * 100);
    if (direction > 0) {
      const next = ZOOM_PRESETS.find((p) => p > current);
      setZoomAboutCenter(next ?? Math.min(current + 25, MAX_ZOOM * 100));
    } else {
      const next = [...ZOOM_PRESETS].reverse().find((p) => p < current);
      setZoomAboutCenter(next ?? Math.max(current - 25, MIN_ZOOM * 100));
    }
  };

  const openZoomTip = () => setZoomTipOpen(true);

  const closeZoomTip = () => {
    if (!zoomTipPinnedRef.current) setZoomTipOpen(false);
  };

  const dismissZoomTip = () => {
    zoomTipPinnedRef.current = false;
    setZoomTipOpen(false);
  };

  const toggleZoomTipPin = () => {
    if (zoomTipPinnedRef.current && zoomTipOpen) {
      dismissZoomTip();
    } else {
      zoomTipPinnedRef.current = true;
      setZoomTipOpen(true);
    }
  };

  // Reset to fit-all whenever the fitted size changes (map load / rotate).
  useEffect(() => {
    setView({ x: 0, y: 0, w: svgW, h: svgH });
    setFitModeIndex(FIT_MODES.indexOf('nodes'));
  }, [svgW, svgH]);

  const setViewFromBounds = (bounds: BoundsPx) => {
    const viewW = bounds.maxX - bounds.minX;
    const viewH = bounds.maxY - bounds.minY;
    setView({ x: bounds.minX, y: bounds.minY, w: viewW, h: viewH });
  };

  const fitMap50 = () => {
    let cx = svgW / 2;
    let cy = svgH / 2;
    if (mapImage) {
      const mapBounds = mapImageBoundsPx(mapImage, toPx);
      cx = (mapBounds.minX + mapBounds.maxX) / 2;
      cy = (mapBounds.minY + mapBounds.maxY) / 2;
    }
    const newW = clampViewWidth(svgW / MIN_ZOOM);
    const newH = newW * (svgH / svgW);
    setView({ x: cx - newW / 2, y: cy - newH / 2, w: newW, h: newH });
  };

  const fitRobots = () => {
    const points = agvs
      .filter((agv) => agv.has_pose && agv.x != null && agv.y != null)
      .map((agv) => toPx(agv.x!, agv.y!));
    const bounds = boundsFromPoints(points);
    if (!bounds) {
      fitNodes();
      return;
    }
    setViewFromBounds(expandBounds(bounds, FIT_PADDING));
  };

  const fitNodes = () => {
    const points = nodes.map((n) => toPx(n.x, n.y));
    const bounds = boundsFromPoints(points);
    if (!bounds) {
      setView({ x: 0, y: 0, w: svgW, h: svgH });
      return;
    }
    setViewFromBounds(expandBounds(bounds, FIT_PADDING));
  };

  const applyFit = (mode: FitMode) => {
    if (mode === 'map') fitMap50();
    else if (mode === 'robots') fitRobots();
    else fitNodes();
  };

  const cycleFit = () => {
    const nextIndex = (fitModeIndex + 1) % FIT_MODES.length;
    const mode = FIT_MODES[nextIndex]!;
    applyFit(mode);
    setFitModeIndex(nextIndex);
  };

  const currentFitMode = FIT_MODES[fitModeIndex]!;

  // Wheel zoom about the cursor. Native non-passive listener so preventDefault
  // actually suppresses page scroll.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const { x, y, w, h } = viewRef.current;
      const fracX = (e.clientX - rect.left) / rect.width;
      const fracY = (e.clientY - rect.top) / rect.height;
      const vx = x + fracX * w;
      const vy = y + fracY * h;
      const raw = w * (e.deltaY > 0 ? 1.1 : 1 / 1.1);
      const newW = clampViewWidth(raw);
      const f = newW / w;
      const newH = h * f;
      setView({ x: vx - fracX * newW, y: vy - fracY * newH, w: newW, h: newH });
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, [svgW]);

  // Click-drag to pan. Tracks distance so a real drag suppresses the trailing
  // click (which would otherwise set a goal / arm a robot).
  const onMouseDown = (e: React.MouseEvent) => {
    const svg = svgRef.current;
    if (!svg) return;
    suppressClickRef.current = false;
    const rect = svg.getBoundingClientRect();
    const start = { cx: e.clientX, cy: e.clientY, ...viewRef.current };
    const k = start.w / rect.width; // viewBox units per client pixel
    setGrabbing(true);
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - start.cx;
      const dy = ev.clientY - start.cy;
      if (Math.hypot(dx, dy) > DRAG_THRESHOLD) suppressClickRef.current = true;
      setView({
        x: start.x - dx * k,
        y: start.y - dy * k,
        w: start.w,
        h: start.h,
      });
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      setGrabbing(false);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  // Swallow the click that ends a pan; let genuine clicks through.
  const handlePickNode = (id: string) => {
    if (suppressClickRef.current) return;
    onPickNode(id);
  };
  const handleSelectRobot = (id: SchedulerRobotId) => {
    if (suppressClickRef.current) return;
    onSelectRobot(id);
  };

  const zoomPct = Math.round((svgW / view.w) * 100);

  const axisLen = 32;
  const axisStroke = 3;
  const axisFont = 12;
  const axisArrow = 9;
  const axisLabelGap = 14;
  const axisDotR = 4;
  const axisEdgePad = 5;
  const axisOrigin = { x: axisEdgePad + axisDotR, y: axisEdgePad + axisDotR };
  const overlayXTip = {
    x: axisOrigin.x + axis.xDir.x * axisLen,
    y: axisOrigin.y + axis.xDir.y * axisLen,
  };
  const overlayYTip = {
    x: axisOrigin.x + axis.yDir.x * axisLen,
    y: axisOrigin.y + axis.yDir.y * axisLen,
  };
  const overlayXLabel = {
    x: overlayXTip.x + axis.xDir.x * axisLabelGap,
    y: overlayXTip.y + axis.xDir.y * axisLabelGap,
  };
  const overlayYLabel = {
    x: overlayYTip.x + axis.yDir.x * axisLabelGap,
    y: overlayYTip.y + axis.yDir.y * axisLabelGap,
  };
  const textExtent = axisFont * 1.25;
  const axisBoundsPoints = [
    axisOrigin,
    overlayXTip,
    overlayYTip,
    overlayXLabel,
    overlayYLabel,
    {
      x: overlayXTip.x + axis.xDir.x * axisArrow,
      y: overlayXTip.y + axis.xDir.y * axisArrow,
    },
    {
      x: overlayYTip.x + axis.yDir.x * axisArrow,
      y: overlayYTip.y + axis.yDir.y * axisArrow,
    },
    { x: axisOrigin.x - axisDotR, y: axisOrigin.y - axisDotR },
    { x: axisOrigin.x + axisDotR, y: axisOrigin.y + axisDotR },
    {
      x: overlayXLabel.x + axis.xDir.x * textExtent * 2,
      y: overlayXLabel.y + axis.xDir.y * textExtent * 2,
    },
    {
      x: overlayYLabel.x + axis.yDir.x * textExtent * 2,
      y: overlayYLabel.y + axis.yDir.y * textExtent * 2,
    },
    { x: overlayXLabel.x - textExtent, y: overlayXLabel.y - textExtent },
    { x: overlayXLabel.x + textExtent, y: overlayXLabel.y + textExtent },
    { x: overlayYLabel.x - textExtent, y: overlayYLabel.y - textExtent },
    { x: overlayYLabel.x + textExtent, y: overlayYLabel.y + textExtent },
  ];
  let axisMinX = Infinity;
  let axisMinY = Infinity;
  let axisMaxX = -Infinity;
  let axisMaxY = -Infinity;
  for (const p of axisBoundsPoints) {
    axisMinX = Math.min(axisMinX, p.x);
    axisMinY = Math.min(axisMinY, p.y);
    axisMaxX = Math.max(axisMaxX, p.x);
    axisMaxY = Math.max(axisMaxY, p.y);
  }
  const axisViewX = axisMinX - axisEdgePad;
  const axisViewY = axisMinY - axisEdgePad;
  const axisViewW = axisMaxX - axisMinX + 2 * axisEdgePad;
  const axisViewH = axisMaxY - axisMinY + 2 * axisEdgePad;
  const axisDisplayScale = 128 / Math.max(axisViewW, axisViewH);
  const axisDisplayW = Math.round(axisViewW * axisDisplayScale);
  const axisDisplayH = Math.round(axisViewH * axisDisplayScale);

  // node_id -> which robots target it (any queued leg), and whether any of
  // those legs are applied.
  const goalByNode = new Map<
    string,
    { robots: SchedulerRobotId[]; applied: boolean }
  >();
  for (const robot of Object.keys(goals) as SchedulerRobotId[]) {
    const goal = goals[robot];
    if (!goal) continue;
    const entry = goalByNode.get(goal.node) ?? { robots: [], applied: false };
    if (!entry.robots.includes(robot)) entry.robots.push(robot);
    entry.applied = entry.applied || goal.applied;
    goalByNode.set(goal.node, entry);
  }

  // Each robot's current graph node (last reported node, else snapped pose),
  // remapped to a rack's approach node when parked at a rack after pick/drop.
  const robotCurrentNode: Partial<Record<SchedulerRobotId, string | null>> = {};
  for (const agv of agvs) {
    const id = toSchedulerId(agv);
    if (!id) continue;
    const raw =
      agv.last_node_id ??
      (agv.has_pose && agv.x != null && agv.y != null
        ? snapToNode(agv.x, agv.y, nodes)
        : null);
    robotCurrentNode[id] = logicalGraphNode(raw, racks);
  }

  // Remaining route per robot: current node chained through each queued goal,
  // in the robot's colour. Recomputed from the live current node each render,
  // so passed legs shrink away as the robot advances.
  const adjacency = buildAdjacency(map?.edges ?? []);
  const routeSegments = (Object.keys(goals) as SchedulerRobotId[]).flatMap(
    (robot) => {
      const goal = goals[robot];
      const start = robotCurrentNode[robot];
      if (!goal || !start) return [];
      const color = ROBOT_COLOR_BY_ID[robot] ?? '#718096';
      const style = robotStyle(robot);
      const path = shortestPath(adjacency, start, goal.node);
      const segs = [];
      for (let k = 0; k < path.length - 1; k++) {
        const a = nodeById.get(path[k]);
        const b = nodeById.get(path[k + 1]);
        if (!a || !b) continue;
        const p1 = toPx(a.x, a.y);
        const p2 = toPx(b.x, b.y);
        segs.push(
          <line
            key={`route-${robot}-${goal.node}-${path[k]}-${path[k + 1]}`}
            x1={p1.x}
            y1={p1.y}
            x2={p2.x}
            y2={p2.y}
            stroke={color}
            strokeWidth={style.routeWidth}
            strokeLinecap="round"
            opacity={style.routeOpacity}
          />,
        );
      }
      return segs;
    },
  );

  return (
    <Box
      position="relative"
      borderWidth="1px"
      borderRadius="lg"
      bg="white"
      overflow="hidden"
      maxW="100%"
      h="100%"
      display="flex"
      flexDirection="column"
    >
      {nodes.length === 0 ? (
        <Text color="gray.500">Waiting for map from the VDA master…</Text>
      ) : (
        <>
          <Box
            position="absolute"
            top={2}
            left={2}
            zIndex={1}
            pointerEvents="none"
          >
            <Box
              bg="white"
              borderRadius="md"
              px={2}
              py={1}
              flexShrink={0}
              pointerEvents="auto"
              display="inline-block"
              lineHeight={0}
            >
              <svg
                width={axisDisplayW}
                height={axisDisplayH}
                viewBox={`${axisViewX} ${axisViewY} ${axisViewW} ${axisViewH}`}
                aria-hidden
              >
                <line
                  x1={axisOrigin.x}
                  y1={axisOrigin.y}
                  x2={overlayXTip.x}
                  y2={overlayXTip.y}
                  stroke="#e53e3e"
                  strokeWidth={axisStroke}
                  strokeLinecap="round"
                />
                <polygon
                  points={axisArrowHead(
                    overlayXTip.x,
                    overlayXTip.y,
                    axisOrigin.x,
                    axisOrigin.y,
                    axisArrow,
                  )}
                  fill="#e53e3e"
                />
                <text
                  x={overlayXLabel.x}
                  y={overlayXLabel.y}
                  fontSize={axisFont}
                  fontWeight={800}
                  fill="#e53e3e"
                >
                  +x
                </text>
                <line
                  x1={axisOrigin.x}
                  y1={axisOrigin.y}
                  x2={overlayYTip.x}
                  y2={overlayYTip.y}
                  stroke="#38a169"
                  strokeWidth={axisStroke}
                  strokeLinecap="round"
                />
                <polygon
                  points={axisArrowHead(
                    overlayYTip.x,
                    overlayYTip.y,
                    axisOrigin.x,
                    axisOrigin.y,
                    axisArrow,
                  )}
                  fill="#38a169"
                />
                <text
                  x={overlayYLabel.x}
                  y={overlayYLabel.y}
                  fontSize={axisFont}
                  fontWeight={800}
                  fill="#38a169"
                >
                  +y
                </text>
                <circle
                  cx={axisOrigin.x}
                  cy={axisOrigin.y}
                  r={axisDotR}
                  fill="#718096"
                />
              </svg>
            </Box>
          </Box>
          <Box
            position="absolute"
            top={2}
            right={2}
            left={2}
            zIndex={1}
            display="flex"
            justifyContent="flex-end"
            pointerEvents="none"
          >
            <HStack
              gap={2}
              bg="white"
              borderRadius="md"
              px={3}
              py={1.5}
              maxW="100%"
              flexShrink={0}
              pointerEvents="auto"
            >
              <Tooltip content="Zoom out" showArrow>
                <IconButton
                  aria-label="Zoom out"
                  size="xs"
                  variant="outline"
                  flexShrink={0}
                  onClick={() => stepZoom(-1)}
                >
                  −
                </IconButton>
              </Tooltip>
              <ToggleTip
                manualTrigger
                open={zoomTipOpen}
                onOpenChange={(e) => {
                  if (!e.open) dismissZoomTip();
                }}
                showArrow
                content={
                  <HStack gap={0.5}>
                    {ZOOM_PRESETS.map((preset) => (
                      <Button
                        key={preset}
                        size="2xs"
                        variant={zoomPct === preset ? 'solid' : 'ghost'}
                        bg={zoomPct === preset ? 'black' : undefined}
                        color={zoomPct === preset ? 'white' : undefined}
                        _hover={
                          zoomPct === preset ? { bg: 'gray.800' } : undefined
                        }
                        onClick={() => {
                          setZoomAboutCenter(preset);
                          dismissZoomTip();
                        }}
                      >
                        {preset}%
                      </Button>
                    ))}
                  </HStack>
                }
                contentProps={{
                  onMouseEnter: openZoomTip,
                  onMouseLeave: closeZoomTip,
                }}
              >
                <Button
                  size="xs"
                  variant="ghost"
                  fontSize="xs"
                  fontWeight={600}
                  color="gray.700"
                  minW="3.5em"
                  px={2}
                  onMouseEnter={openZoomTip}
                  onMouseLeave={closeZoomTip}
                  onClick={toggleZoomTipPin}
                >
                  {zoomPct}%
                </Button>
              </ToggleTip>
              <Tooltip content="Zoom in" showArrow>
                <IconButton
                  aria-label="Zoom in"
                  size="xs"
                  variant="outline"
                  flexShrink={0}
                  onClick={() => stepZoom(1)}
                >
                  +
                </IconButton>
              </Tooltip>
              {onToggleRotate && (
                <Tooltip content="Rotate map 90°" showArrow>
                  <IconButton
                    aria-label="Rotate map 90°"
                    size="xs"
                    variant={rotated ? 'solid' : 'outline'}
                    bg={rotated ? 'black' : undefined}
                    color={rotated ? 'white' : undefined}
                    _hover={rotated ? { bg: 'gray.800' } : undefined}
                    flexShrink={0}
                    onClick={onToggleRotate}
                    css={{
                      _icon: {
                        width: '14px',
                        height: '14px',
                      },
                    }}
                  >
                    <RotateCcwIcon />
                  </IconButton>
                </Tooltip>
              )}
              <Button
                size="xs"
                variant="solid"
                bg="black"
                color="white"
                _hover={{ bg: 'gray.800' }}
                flexShrink={0}
                aria-label={FIT_MODE_LABEL[currentFitMode]}
                onClick={cycleFit}
              >
                {FIT_MODE_LABEL[currentFitMode]}
              </Button>
            </HStack>
          </Box>
          <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
            preserveAspectRatio="xMidYMid meet"
            onMouseDown={onMouseDown}
            style={{
              flex: '1 1 auto',
              minHeight: 0,
              width: '100%',
              height: '100%',
              display: 'block',
              touchAction: 'none',
              cursor: grabbing ? 'grabbing' : 'grab',
            }}
          >
            {/* Master-frame map image backdrop (aligned via the shared toPx). */}
            {mapImage && (
              <image
                href={mapImage.url}
                x={0}
                y={0}
                width={mapImage.width}
                height={mapImage.height}
                transform={imageTransform(mapImage, toPx)}
                preserveAspectRatio="none"
                style={{ pointerEvents: 'none' }}
              />
            )}
            {/* Edges */}
            {(map?.edges ?? []).map((e) => {
              const a = nodeById.get(e.start_node_id);
              const b = nodeById.get(e.end_node_id);
              if (!a || !b) return null;
              const p1 = toPx(a.x, a.y);
              const p2 = toPx(b.x, b.y);
              return (
                <line
                  key={e.edge_id}
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke="#cbd5e0"
                  strokeWidth={VISUAL.edgeWidth}
                />
              );
            })}
            {/* Remaining route per robot (robot colour), under the nodes. */}
            {routeSegments}
            {/* Nodes with id + coordinates (labels stay level). Click = set goal. */}
            {nodes.map((n) => {
              const p = toPx(n.x, n.y);
              const goal = goalByNode.get(n.node_id);
              const isGoal = goal != null;
              // Rack node (load handling): AutoXing pick/drop via rack-direct.
              const isRack = n.node_id in racks;
              // Goal node: filled in the owning robot's colour (blue/orange) with
              // a gold ring + gold "G" so it reads as a goal and shows whose.
              const goalColor = goal ? ROBOT_COLOR_BY_ID[goal.robots[0]] : null;
              return (
                <g
                  key={n.node_id}
                  onClick={() => handlePickNode(n.node_id)}
                  style={{ cursor: 'pointer' }}
                >
                  {isRack && (
                    <circle
                      cx={p.x}
                      cy={p.y}
                      r={VISUAL.goalNodeRadius + 3}
                      fill="none"
                      stroke="#805ad5"
                      strokeWidth={1.5}
                      strokeDasharray="2 2"
                    />
                  )}
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={isGoal ? VISUAL.goalNodeRadius : VISUAL.nodeRadius}
                    fill={goalColor ?? '#4a5568'}
                    stroke={isGoal ? GOAL_GOLD : 'none'}
                    strokeWidth={
                      isGoal
                        ? goal!.applied
                          ? VISUAL.goalAppliedRingWidth
                          : VISUAL.goalRingWidth
                        : 0
                    }
                  />
                  {isRack && (
                    <text
                      x={p.x - VISUAL.goalNodeRadius - 2}
                      y={p.y - VISUAL.goalNodeRadius + 2}
                      textAnchor="middle"
                      fontSize={VISUAL.goalMarkSize}
                      fontWeight={800}
                      fill="#805ad5"
                      style={{ textShadow: TEXT_SHADOW }}
                    >
                      R
                    </text>
                  )}
                  <text
                    x={p.x}
                    y={p.y - VISUAL.goalNodeRadius - 2}
                    textAnchor="middle"
                    fontSize={VISUAL.nodeLabelSize}
                    fontWeight={600}
                    fill="#2d3748"
                    style={{ textShadow: TEXT_SHADOW }}
                  >
                    {n.node_id}
                  </text>
                  {isGoal && (
                    <text
                      x={p.x + VISUAL.goalNodeRadius + 2}
                      y={p.y - VISUAL.goalNodeRadius + 2}
                      textAnchor="middle"
                      fontSize={VISUAL.goalMarkSize}
                      fontWeight={800}
                      fill={GOAL_GOLD}
                      style={{ textShadow: TEXT_SHADOW }}
                    >
                      G
                    </text>
                  )}
                  <text
                    x={p.x}
                    y={p.y + VISUAL.goalNodeRadius + VISUAL.coordLabelSize}
                    textAnchor="middle"
                    fontSize={VISUAL.coordLabelSize}
                    fill="#718096"
                    style={{ textShadow: TEXT_SHADOW }}
                  >
                    ({n.x.toFixed(1)}, {n.y.toFixed(1)})
                  </text>
                </g>
              );
            })}
            {/* Robots: arrow at (x, y), rotated by theta (rad). Click = arm. */}
            {agvs.map((agv, i) => {
              if (!agv.has_pose || agv.x == null || agv.y == null) return null;
              const color = robotColor(agv, i);
              const p = toPx(agv.x, agv.y);
              const deg = robotDeg(agv.theta ?? 0);
              const schedId = toSchedulerId(agv);
              const isSelected = schedId != null && schedId === selectedRobot;
              const style = robotStyle(schedId);
              return (
                <g
                  key={agv.robot_id}
                  onClick={() => schedId && handleSelectRobot(schedId)}
                  style={{ cursor: schedId ? 'pointer' : 'default' }}
                >
                  <g transform={`translate(${p.x}, ${p.y})`}>
                    {isSelected && (
                      <circle
                        r={style.ringRadius}
                        fill="none"
                        stroke={SELECTED_COLOR}
                        strokeWidth={style.ringWidth}
                      />
                    )}
                    <circle r={style.robotRadius} fill={color} opacity={0.25} />
                    <polygon
                      points="12,0 -7,7 -7,-7"
                      fill={color}
                      transform={`rotate(${deg}) scale(${style.arrowScale})`}
                    />
                  </g>
                  <text
                    x={p.x}
                    y={p.y - style.ringRadius - 2}
                    textAnchor="middle"
                    fontSize={style.labelSize}
                    fontWeight={700}
                    fill={color}
                    style={{ textShadow: TEXT_SHADOW }}
                  >
                    {agv.robot_id}
                  </text>
                </g>
              );
            })}
          </svg>
        </>
      )}
    </Box>
  );
}

export default MapCanvas;
