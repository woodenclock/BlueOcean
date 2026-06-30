import * as THREE from 'three';
import { DEFAULT_NAV_OVERLAY_CONFIG } from './config';
import { GoalMarker } from './goal-marker';
import {
  buildPathPipe,
  disposePipeGroup,
  pathPointToVector3,
} from './path-geometry';
import { PoseSimulator } from './pose-simulator';
import { RobotMarker } from './robot-marker';
import type {
  NavOverlayConfig,
  NavOverlayEvents,
  PathDefinition,
  RobotPose,
} from './types';
import {
  createWaypointMarkers,
  disposeWaypointMarkers,
  setWaypointVisited,
  type WaypointMarkerEntry,
} from './waypoint-markers';

export type NavigationOverlayOptions = {
  scene: THREE.Scene;
  config?: Partial<NavOverlayConfig>;
  pathUrl?: string;
  pathDefinition?: PathDefinition;
  domElement: HTMLElement;
  camera: THREE.Camera;
};

type Listener<K extends keyof NavOverlayEvents> = (
  event: NavOverlayEvents[K],
) => void;

export class NavigationOverlay {
  readonly group = new THREE.Group();

  private readonly config: NavOverlayConfig;
  private readonly domElement: HTMLElement;
  private readonly camera: THREE.Camera;
  private clock = new THREE.Clock();
  private readonly listeners = new Map<
    keyof NavOverlayEvents,
    Set<Listener<keyof NavOverlayEvents>>
  >();

  private worldPoints: THREE.Vector3[] = [];
  private pathIds: number[] = [];
  private pipeGroup: THREE.Group | null = null;
  private pipeMaterials: ReturnType<typeof buildPathPipe>['materials'] | null =
    null;
  private segmentDirections: THREE.Vector3[] = [];
  private segmentStarts: THREE.Vector3[] = [];
  private segmentEnds: THREE.Vector3[] = [];
  private robot: RobotMarker | null = null;
  private goal: GoalMarker | null = null;
  private waypoints: WaypointMarkerEntry[] = [];
  private simulator: PoseSimulator | null = null;
  private clipPlane = new THREE.Plane();
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private running = false;
  private enabled = false;
  private hasArrived = false;

  private constructor(
    config: NavOverlayConfig,
    domElement: HTMLElement,
    camera: THREE.Camera,
  ) {
    this.config = config;
    this.domElement = domElement;
    this.camera = camera;
    this.onPointerDown = this.onPointerDown.bind(this);
  }

  static async create(
    options: NavigationOverlayOptions,
  ): Promise<NavigationOverlay> {
    const config = {
      ...DEFAULT_NAV_OVERLAY_CONFIG,
      ...options.config,
    };
    const overlay = new NavigationOverlay(
      config,
      options.domElement,
      options.camera,
    );

    let definition = options.pathDefinition;
    if (!definition) {
      const url = options.pathUrl ?? '/navigation-path.json';
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Failed to load path: ${res.status}`);
      definition = (await res.json()) as PathDefinition;
    }

    overlay.build(definition);
    options.scene.add(overlay.group);
    overlay.domElement.addEventListener('pointerdown', overlay.onPointerDown);
    return overlay;
  }

  on<K extends keyof NavOverlayEvents>(
    type: K,
    listener: Listener<K>,
  ): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener as Listener<keyof NavOverlayEvents>);
    return () =>
      this.listeners
        .get(type)
        ?.delete(listener as Listener<keyof NavOverlayEvents>);
  }

  private emit<K extends keyof NavOverlayEvents>(
    type: K,
    payload: NavOverlayEvents[K],
  ) {
    this.listeners.get(type)?.forEach((fn) => {
      (fn as Listener<K>)(payload);
    });
  }

  private build(definition: PathDefinition) {
    const { path } = definition;
    if (path.length < 2) return;

    this.worldPoints = path.map((p) => pathPointToVector3(p));
    this.pathIds = path.map((p) => p.id);
    const pipe = buildPathPipe(this.worldPoints, this.config);
    this.pipeGroup = pipe.group;
    this.pipeMaterials = pipe.materials;
    this.segmentDirections = pipe.segmentDirections;
    this.segmentStarts = pipe.segmentStarts;
    this.segmentEnds = pipe.segmentEnds;
    this.group.add(pipe.group);

    this.robot = new RobotMarker(this.config);
    this.group.add(this.robot.group);

    this.goal = new GoalMarker(this.config);
    this.goal.setPosition(this.worldPoints[this.worldPoints.length - 1]);
    this.group.add(this.goal.group);

    this.waypoints = createWaypointMarkers(path, this.worldPoints, this.config);
    for (const wp of this.waypoints) {
      this.group.add(wp.group);
    }

    this.simulator = new PoseSimulator(
      this.worldPoints,
      this.pathIds,
      this.config,
      {
        onWaypointReached: (waypointId, pathIndex) => {
          this.emit('robot:waypointReached', { waypointId });
          const wp = this.waypoints.find((w) => w.id === waypointId);
          if (wp) setWaypointVisited(wp, true, this.config);
          void pathIndex;
        },
        onArrived: (goalId) => {
          this.hasArrived = true;
          this.goal?.triggerArrival();
          this.robot?.setColorState('arrived');
          this.emit('robot:arrived', { goalId });
        },
      },
    );

    this.reset();
  }

  start() {
    this.setEnabled(true);
  }

  isEnabled() {
    return this.enabled;
  }

  setEnabled(enabled: boolean) {
    if (enabled) {
      this.group.visible = true;
      this.reset();
      this.clock = new THREE.Clock();
      this.clock.start();
      this.running = true;
      this.enabled = true;
    } else {
      this.running = false;
      this.enabled = false;
      this.group.visible = false;
      this.clock.stop();
    }
  }

  tick(delta?: number) {
    if (!this.enabled || !this.running || !this.simulator || !this.robot)
      return;

    const dt = delta ?? this.clock.getDelta();
    const elapsed = this.clock.getElapsedTime();
    const pose = this.simulator.step(dt);

    this.applyPose(pose);
    this.updatePipeMaterials(pose);
    this.updateWaypointStates(pose);
    this.goal?.update(elapsed);
  }

  reset() {
    this.simulator?.reset();
    this.hasArrived = false;
    this.goal?.reset();
    this.robot?.setColorState('moving');

    if (this.worldPoints.length > 0 && this.robot) {
      const start = this.worldPoints[0];
      this.robot.setPosition(start.x, start.y, start.z);
      this.robot.setHeading(0);
    }

    for (const wp of this.waypoints) {
      setWaypointVisited(wp, false, this.config);
    }

    this.applyPipeState(-1, 0);
    this.emit('path:reset', {});
  }

  private applyPose(pose: RobotPose) {
    if (!this.robot) return;

    this.robot.setPosition(pose.x, pose.y, pose.z);
    this.robot.setHeading(pose.heading);

    const state = this.hasArrived
      ? 'arrived'
      : pose.speed > 0.05
        ? 'moving'
        : 'idle';
    this.robot.setColorState(state);
  }

  private updatePipeMaterials(pose: RobotPose) {
    this.applyPipeState(pose.currentSegment, pose.segmentProgress);
  }

  private applyPipeState(currentSegment: number, segmentProgress: number) {
    if (!this.pipeGroup || !this.pipeMaterials) return;

    const { pending, traversed, active } = this.pipeMaterials;

    if (currentSegment >= 0 && currentSegment < this.segmentDirections.length) {
      const dir = this.segmentDirections[currentSegment];
      const start = this.segmentStarts[currentSegment];
      const end = this.segmentEnds[currentSegment];
      const point = start.clone().lerp(end, segmentProgress);
      this.clipPlane.setFromNormalAndCoplanarPoint(dir.clone().negate(), point);
      active.clippingPlanes = [this.clipPlane];
    } else {
      active.clippingPlanes = [];
    }

    this.pipeGroup.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      const data = child.userData;
      if (!data?.isPipe) return;

      const seg = data.segmentIndex as number;
      let mat: THREE.MeshStandardMaterial;
      if (seg < currentSegment) {
        mat = traversed;
      } else if (seg === currentSegment) {
        mat = active;
      } else {
        mat = pending;
      }

      if (child.material !== mat) {
        child.material = mat;
      }
    });
  }

  private updateWaypointStates(pose: RobotPose) {
    for (let i = 0; i < this.waypoints.length; i++) {
      const pathIndex = i + 1;
      const visited = pathIndex <= pose.currentSegment;
      setWaypointVisited(this.waypoints[i], visited, this.config);
    }
  }

  private onPointerDown(event: PointerEvent) {
    if (!this.enabled || this.waypoints.length === 0) return;

    const rect = this.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, this.camera);
    const meshes = this.waypoints.map((w) => w.mesh);
    const hits = this.raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return;

    const hit = hits[0].object;
    const id = (hit.userData as { waypointId?: number }).waypointId;
    if (id !== undefined) {
      this.emit('waypoint:selected', { waypointId: id });
    }
  }

  dispose() {
    this.domElement.removeEventListener('pointerdown', this.onPointerDown);
    this.running = false;

    if (this.pipeGroup) {
      disposePipeGroup(this.pipeGroup);
      this.pipeGroup = null;
    }

    this.pipeMaterials?.pending.dispose();
    this.pipeMaterials?.traversed.dispose();
    this.pipeMaterials?.active.dispose();
    this.pipeMaterials = null;

    this.robot?.dispose();
    this.goal?.dispose();
    disposeWaypointMarkers(this.waypoints);

    this.group.removeFromParent();
    this.listeners.clear();
  }
}
