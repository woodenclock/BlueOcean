// Planner-frame (metres, y-up) -> SVG pixel (y-down) projection, plus the
// optional 90° rotation. Pure geometry — no React.
import type { MapImageMeta, MapNode } from '../types';

// Pixels per planner-frame metre, plus padding around the map bounds.
export const SCALE = 45;
export const PAD = 0.8;

export const AXIS_MARGIN = 18;
export const AXIS_LEN_PX = 36;

export interface Vec2 {
  x: number;
  y: number;
}

export function normDir(dx: number, dy: number): Vec2 {
  const len = Math.hypot(dx, dy) || 1;
  return { x: dx / len, y: dy / len };
}

export function axisArrowHead(
  tipX: number,
  tipY: number,
  fromX: number,
  fromY: number,
  size = 7,
) {
  const dx = tipX - fromX;
  const dy = tipY - fromY;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = -uy;
  const py = ux;
  const bx = tipX - ux * size;
  const by = tipY - uy * size;
  return `${tipX},${tipY} ${bx + px * (size * 0.45)},${by + py * (size * 0.45)} ${bx - px * (size * 0.45)},${by - py * (size * 0.45)}`;
}

export interface BoundsPx {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface Projection {
  svgW: number;
  svgH: number;
  toPx: (x: number, y: number) => Vec2;
  // Arrow mesh points +x at 0°; VDA theta is π rad off from the drawn heading.
  robotDeg: (theta: number) => number;
  axis: {
    origin: Vec2;
    xTip: Vec2;
    yTip: Vec2;
    xDir: Vec2;
    yDir: Vec2;
  };
}

// SVG transform that maps the map image's local pixel rect — u in [0, width]
// (right), v in [0, height] (down), top-left at (0, 0) — into screen space via
// `toPx`, so the backdrop inherits the same y-flip and 90° rotation as the
// nodes. ROS map_server: `origin` is the world pose of the image's lower-left
// corner, so world_x = ox + u*res and world_y = oy + (height - v)*res.
export function imageTransform(
  meta: MapImageMeta,
  toPx: (x: number, y: number) => Vec2,
): string {
  const { width: W, height: H, resolution: r } = meta;
  const [ox, oy] = meta.origin;
  const p00 = toPx(ox, oy + H * r); // image top-left  (u=0,   v=0)
  const p10 = toPx(ox + W * r, oy + H * r); // image top-right (u=W,   v=0)
  const p01 = toPx(ox, oy); // image bottom-left (u=0, v=H)
  const a = (p10.x - p00.x) / W;
  const b = (p10.y - p00.y) / W;
  const c = (p01.x - p00.x) / H;
  const d = (p01.y - p00.y) / H;
  return `matrix(${a} ${b} ${c} ${d} ${p00.x} ${p00.y})`;
}

export function boundsFromPoints(points: Vec2[]): BoundsPx | null {
  if (points.length === 0) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of points) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  return { minX, minY, maxX, maxY };
}

export function mapImageBoundsPx(
  meta: MapImageMeta,
  toPx: (x: number, y: number) => Vec2,
): BoundsPx {
  const { width: W, height: H, resolution: r } = meta;
  const [ox, oy] = meta.origin;
  const corners = [
    toPx(ox, oy),
    toPx(ox + W * r, oy),
    toPx(ox, oy + H * r),
    toPx(ox + W * r, oy + H * r),
  ];
  return boundsFromPoints(corners)!;
}

export function expandBounds(bounds: BoundsPx, paddingRatio: number): BoundsPx {
  const spanX = bounds.maxX - bounds.minX;
  const spanY = bounds.maxY - bounds.minY;
  const padX = Math.max(spanX * paddingRatio, 1);
  const padY = Math.max(spanY * paddingRatio, 1);
  return {
    minX: bounds.minX - padX,
    minY: bounds.minY - padY,
    maxX: bounds.maxX + padX,
    maxY: bounds.maxY + padY,
  };
}

// Fit bounds come from the STATIC map nodes only — never live AGV poses.
// Folding in moving robots would shift svgW/svgH every state frame, which
// re-fits (and visibly yanks) the view on each WebSocket update.
export function computeProjection(
  nodes: MapNode[],
  rotated: boolean,
): Projection {
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 1;
  const minY = ys.length ? Math.min(...ys) : 0;
  const maxY = ys.length ? Math.max(...ys) : 1;

  const sx = (x: number) => (x - minX + PAD) * SCALE;
  const sy = (y: number) => (maxY + PAD - y) * SCALE;
  const width = (maxX - minX + 2 * PAD) * SCALE;
  const height = (maxY - minY + 2 * PAD) * SCALE;

  // Rotate geometry 90° CCW; labels stay upright via screen-space offsets.
  const toPx = (x: number, y: number): Vec2 => {
    const cx = sx(x);
    const cy = sy(y);
    return rotated ? { x: height - cy, y: cx } : { x: cx, y: cy };
  };

  const robotDeg = (theta: number) => {
    const deg = (-theta * 180) / Math.PI + 180;
    const heading = rotated ? deg + 90 : deg;
    return heading + 180;
  };

  const origin = toPx(0, 0);
  const xDir = normDir(toPx(1, 0).x - origin.x, toPx(1, 0).y - origin.y);
  const yDir = normDir(toPx(0, 1).x - origin.x, toPx(0, 1).y - origin.y);
  const axisOrigin = { x: AXIS_MARGIN, y: AXIS_MARGIN };

  return {
    svgW: rotated ? height : width,
    svgH: rotated ? width : height,
    toPx,
    robotDeg,
    axis: {
      origin: axisOrigin,
      xTip: {
        x: axisOrigin.x + xDir.x * AXIS_LEN_PX,
        y: axisOrigin.y + xDir.y * AXIS_LEN_PX,
      },
      yTip: {
        x: axisOrigin.x + yDir.x * AXIS_LEN_PX,
        y: axisOrigin.y + yDir.y * AXIS_LEN_PX,
      },
      xDir,
      yDir,
    },
  };
}
