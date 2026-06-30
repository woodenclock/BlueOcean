type StringObj = {
  value?: string;
};

type Point2DObj = {
  x: number;
  y: number;
};

type PoseValue = {
  point2D?: Point2DObj;
};

type PoseObj = {
  value?: PoseValue;
};

export type StateMessage = {
  id: string;
  status?: StringObj;
  pose?: PoseObj;
};
