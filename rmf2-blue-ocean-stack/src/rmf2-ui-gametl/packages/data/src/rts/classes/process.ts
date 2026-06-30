export interface Dependency {
  id: string;
  type?: string;
}

export interface GraphElement {
  id: string;
  needs: Dependency[];
}

export interface Process {
  id: string;
  graph: GraphElement[];
}
