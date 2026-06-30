import { useEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Center,
  HStack,
  IconButton,
  Kbd,
  Stack,
  Text,
} from '@chakra-ui/react';
import { LuLocateFixed } from 'react-icons/lu';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { ViewportGizmo } from 'three-viewport-gizmo';

import { Tooltip } from '@/components/ui/tooltip';
import { DropPointMarker } from '../drop-point-marker';

import type {
  DropPointCoords,
  LoadState,
  RobotRuntime,
  RobotStatus,
  SceneDebugInfo,
  SceneViewerApi,
  StaticCollisionBox,
} from './robot-types';

import {
  DRACO_DECODER_PATH,
  ROBOT_ARRIVAL_EPSILON,
  ROBOT_CONFIG_REFRESH_MS,
  ROBOT_MODEL_URL,
  SCENE_URL,
  INITIAL_SHOW_ROOF_SLICE,
  INITIAL_ROOF_SLICE_HEIGHT,
} from './constants';

import { fetchRobotConfigs } from './robot-map-config/robot-config-api';

// import { getInitialRobotPosition } from './robot-map-coordinates/robot-position';
import { getActiveRobotTarget } from './robot-map-coordinates/waypoint-utils';

import { stepDirectlyTowardWaypoint } from './robot-map-motion/direct-waypoint-motion';
import {
  movementHeadingToModelHeading,
  modelHeadingToMovementHeading,
} from './robot-map-motion/robot-heading';

import { toRobotStatus } from './robot-map-runtime/robot-status';
import { tuneMaterials } from './robot-map-runtime/robot-runtime-utils';

import {
  removeRobot,
  syncRobotsFromConfig,
} from './robot-map-runtime/robot-sync';

import { updateRobotTrail } from './robot-map-draw-trail/robot-trail';

import { loadGltfAsync } from './robot-map-scene/gltf-loader';
import {
  computeSceneBounds,
  toSceneDebugInfo,
} from './robot-map-scene/scene-bounds';
import {
  animateIntroCamera,
  computeCameraFrame,
  frameCamera,
} from './robot-map-scene/scene-camera';
import {
  collectStaticCollisionBoxes,
  findRobotCollision,
} from './robot-map-scene/scene-collision';
import { disposeObject3D } from './robot-map-scene/scene-dispose';
import { createGridAxesHelpers } from './robot-map-scene/scene-grid-axis';

import { SceneControlPanel } from './ui/scene-control-panel';
import { DropPointPanel } from './ui/drop-point-panel';
import { RobotStatusPanel } from './ui/robot-status-panel';

function formatCoord(value: number) {
  return value.toFixed(3);
}

export function SceneViewer() {
  const containerRef = useRef<HTMLDivElement>(null);

  const resetOrbitRef = useRef<(() => void) | null>(null);
  const resetRobotsRef = useRef<(() => void) | null>(null);
  const sceneApiRef = useRef<SceneViewerApi | null>(null);

  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [showGridAxes, setShowGridAxes] = useState(false);
  const [showDropPoint, setShowDropPoint] = useState(false);
  const [showRoofSlice, setShowRoofSlice] = useState(INITIAL_SHOW_ROOF_SLICE);
  const [roofSliceHeight, setRoofSliceHeight] = useState(
    INITIAL_ROOF_SLICE_HEIGHT,
  );

  const [dropPoint, setDropPoint] = useState<DropPointCoords>({
    x: 0,
    y: 0,
    z: 0,
  });

  const [sceneDebug, setSceneDebug] = useState<SceneDebugInfo | null>(null);
  const [robotStatuses, setRobotStatuses] = useState<RobotStatus[]>([]);

  const showDropPointRef = useRef(showDropPoint);
  const dropPointRef = useRef(dropPoint);

  showDropPointRef.current = showDropPoint;
  dropPointRef.current = dropPoint;

  useEffect(() => {
    sceneApiRef.current?.setShowGridAxes(showGridAxes);
  }, [showGridAxes, sceneDebug]);

  useEffect(() => {
    sceneApiRef.current?.setDropPointEnabled(showDropPoint);
  }, [showDropPoint, loadState]);

  useEffect(() => {
    sceneApiRef.current?.setDropPointPosition(dropPoint);
  }, [dropPoint, loadState]);

  useEffect(() => {
    sceneApiRef.current?.setRoofSliceEnabled(showRoofSlice);
  }, [showRoofSlice, loadState]);

  useEffect(() => {
    sceneApiRef.current?.setRoofSliceHeight(roofSliceHeight);
  }, [roofSliceHeight, loadState]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);

    const previousDefaultUp = THREE.Object3D.DEFAULT_UP.clone();
    THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

    camera.up.set(0, 0, 1);
    camera.position.set(5, -5, 5);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      logarithmicDepthBuffer: true,
      powerPreference: 'high-performance',
    });

    const roofClipPlane = new THREE.Plane(
      new THREE.Vector3(0, 0, -1),
      INITIAL_ROOF_SLICE_HEIGHT,
    );

    renderer.clippingPlanes = INITIAL_SHOW_ROOF_SLICE ? [roofClipPlane] : [];
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    container.appendChild(renderer.domElement);

    const clock = new THREE.Clock();

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
    directionalLight.position.set(10, 20, 10);
    scene.add(directionalLight);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.zoomSpeed = 2.5;

    const gizmo = new ViewportGizmo(camera, renderer, {
      container: renderer.domElement.parentElement ?? container,
    });

    gizmo.attachControls(controls);

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath(DRACO_DECODER_PATH);

    const loader = new GLTFLoader();
    loader.setDRACOLoader(dracoLoader);

    let animationFrameId = 0;
    let disposed = false;

    let loadedScene: THREE.Group | null = null;
    let gridAxesHelpers: THREE.Group | null = null;
    let dropPointMarker: DropPointMarker | null = null;
    let robotTemplate: THREE.Group | null = null;

    let robotConfigTimerId: number | null = null;
    let staticCollisionBoxes: StaticCollisionBox[] = [];
    let lastRobotStatusPublish = 0;
    let currentFloorZ = 0;

    const robots = new Map<string, RobotRuntime>();

    const pickRaycaster = new THREE.Raycaster();
    const pickPointer = new THREE.Vector2();

    const publishRobotStatuses = (force = false) => {
      const now = performance.now();

      if (!force && now - lastRobotStatusPublish < 250) return;

      lastRobotStatusPublish = now;

      setRobotStatuses(
        Array.from(robots.values()).map((robot) =>
          toRobotStatus(robot, currentFloorZ),
        ),
      );
    };

    const refreshRobotConfig = async (floorZ: number) => {
      const template = robotTemplate;

      if (!template) return;

      try {
        const configs = await fetchRobotConfigs();

        if (disposed) return;

        syncRobotsFromConfig({
          configs,
          scene,
          robots,
          template,
          floorZ,
          publishRobotStatuses,
        });
      } catch (robotConfigError) {
        console.error('Robot config failed to load', robotConfigError);
      }
    };

    const updateRobots = (deltaSeconds: number, floorZ: number) => {
      for (const robot of robots.values()) {
        robot.blockedBy = undefined;
        robot.status = 'idle';

        if (robot.config.enabled === false) {
          robot.status = 'disabled';
          continue;
        }

        const activeTarget = getActiveRobotTarget(robot, floorZ);
        if (!activeTarget) continue;

        const { target } = activeTarget;

        const previousPosition = robot.root.position.clone();
        const previousModelHeading = robot.root.rotation.z;
        const previousMovementHeading =
          modelHeadingToMovementHeading(previousModelHeading);

        const stepResult = stepDirectlyTowardWaypoint({
          current: previousPosition,
          target,
          speed: Math.max(robot.config.speed ?? 1, 0),
          deltaSeconds,
          arrivalEpsilon: ROBOT_ARRIVAL_EPSILON,
          previousHeading: previousMovementHeading,
        });

        robot.root.position.copy(stepResult.position);
        robot.root.rotation.z = movementHeadingToModelHeading(
          stepResult.heading,
        );

        robot.driveState = null;

        const blockedBy = findRobotCollision({
          robot,
          robots,
          staticCollisionBoxes,
        });

        if (blockedBy) {
          robot.root.position.copy(previousPosition);
          robot.root.rotation.z = previousModelHeading;
          robot.driveState = null;
          robot.blockedBy = blockedBy;
          robot.status = 'blocked';
          continue;
        }

        if (stepResult.arrived) {
          const pathLength = robot.config.path?.length ?? 0;

          if (pathLength > 0) {
            if (robot.pathIndex < pathLength - 1) {
              robot.pathIndex += 1;
              robot.status = 'moving';
            } else if (robot.config.loop) {
              robot.pathIndex = 0;
              robot.status = 'moving';
            } else {
              robot.status = 'arrived';
            }
          } else {
            robot.status = 'idle';
          }

          updateRobotTrail(robot, true);
          continue;
        }

        robot.status = 'moving';
        updateRobotTrail(robot);
      }

      publishRobotStatuses();
    };

    const onDropPointPointerDown = (event: PointerEvent) => {
      if (!showDropPointRef.current || !event.altKey || !dropPointMarker) {
        return;
      }

      const rect = renderer.domElement.getBoundingClientRect();

      pickPointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pickPointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      pickRaycaster.setFromCamera(pickPointer, camera);

      const picked = dropPointMarker.pickOnPlane(
        pickRaycaster,
        dropPointRef.current.z,
      );

      if (!picked) return;

      dropPointRef.current = picked;
      dropPointMarker.setPosition(picked);
      setDropPoint(picked);
    };

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;

      if (width === 0 || height === 0) return;

      camera.aspect = width / height;
      camera.updateProjectionMatrix();

      renderer.setSize(width, height);
      gizmo.update();
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    renderer.domElement.addEventListener('pointerdown', onDropPointPointerDown);

    const animate = () => {
      if (disposed) return;

      animationFrameId = requestAnimationFrame(animate);

      const deltaSeconds = clock.getDelta();

      controls.update();
      updateRobots(deltaSeconds, currentFloorZ);

      renderer.render(scene, camera);
      gizmo.render();
    };

    animate();

    loader.load(
      SCENE_URL,
      async (gltf) => {
        if (disposed) return;

        loadedScene = gltf.scene;

        // GLTF is usually Y-up; rotate to Z-up world convention.
        gltf.scene.rotation.x = Math.PI / 2;

        tuneMaterials(gltf.scene);
        scene.add(gltf.scene);

        const bounds = computeSceneBounds(gltf.scene);
        currentFloorZ = bounds.floorZ;

        staticCollisionBoxes = collectStaticCollisionBoxes(
          gltf.scene,
          bounds.floorZ,
        );

        gridAxesHelpers = createGridAxesHelpers(bounds);
        scene.add(gridAxesHelpers);

        dropPointMarker = new DropPointMarker(bounds.maxDim * 0.012);
        scene.add(dropPointMarker.mesh);

        const initialDrop: DropPointCoords = {
          x: (bounds.min.x + bounds.max.x) / 2,
          y: (bounds.min.y + bounds.max.y) / 2,
          z: bounds.floorZ,
        };

        dropPointRef.current = initialDrop;
        dropPointMarker.setPosition(initialDrop);
        setDropPoint(initialDrop);

        sceneApiRef.current = {
          setShowGridAxes(show) {
            if (gridAxesHelpers) {
              gridAxesHelpers.visible = show;
            }
          },

          setDropPointEnabled(enabled) {
            dropPointMarker?.setVisible(enabled);
          },

          setDropPointPosition(position) {
            dropPointMarker?.setPosition(position);
          },

          setRoofSliceEnabled(enabled) {
            renderer.clippingPlanes = enabled ? [roofClipPlane] : [];
          },

          setRoofSliceHeight(height) {
            roofClipPlane.constant = height;
          },
        };

        setSceneDebug(toSceneDebugInfo(bounds));

        const frame = computeCameraFrame(gltf.scene);

        resetOrbitRef.current = () => {
          frameCamera(camera, controls, gltf.scene);
        };

        try {
          robotTemplate = await loadGltfAsync(loader, ROBOT_MODEL_URL);
          tuneMaterials(robotTemplate);

          await refreshRobotConfig(bounds.floorZ);

          robotConfigTimerId = window.setInterval(() => {
            void refreshRobotConfig(bounds.floorZ);
          }, ROBOT_CONFIG_REFRESH_MS);
        } catch (robotError) {
          console.error('Robots failed to load', robotError);
          setRobotStatuses([]);
        }

        if (disposed) return;

        setLoadState('ready');
        animateIntroCamera(camera, controls, frame, () => disposed);
      },
      undefined,
      (error) => {
        if (disposed) return;

        const message =
          error instanceof Error ? error.message : 'Failed to load 3D scene';

        setErrorMessage(message);
        setLoadState('error');
      },
    );

    return () => {
      disposed = true;

      resetOrbitRef.current = null;
      resetRobotsRef.current = null;
      sceneApiRef.current = null;

      if (robotConfigTimerId !== null) {
        window.clearInterval(robotConfigTimerId);
        robotConfigTimerId = null;
      }

      for (const id of Array.from(robots.keys())) {
        removeRobot({
          id,
          scene,
          robots,
        });
      }

      if (robotTemplate) {
        disposeObject3D(robotTemplate);
        robotTemplate = null;
      }

      staticCollisionBoxes = [];
      setRobotStatuses([]);

      renderer.domElement.removeEventListener(
        'pointerdown',
        onDropPointPointerDown,
      );

      dropPointMarker?.dispose();
      dropPointMarker = null;

      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();

      if (gridAxesHelpers) {
        scene.remove(gridAxesHelpers);
        disposeObject3D(gridAxesHelpers);
        gridAxesHelpers = null;
      }

      if (loadedScene) {
        disposeObject3D(loadedScene);
        scene.remove(loadedScene);
        loadedScene = null;
      }

      setSceneDebug(null);

      gizmo.dispose();

      THREE.Object3D.DEFAULT_UP.copy(previousDefaultUp);

      controls.dispose();
      renderer.dispose();
      dracoLoader.dispose();

      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <Box
      ref={containerRef}
      position="relative"
      w="100%"
      h={{ base: '400px', md: '600px', xl: '70vh' }}
      bg="white"
      borderWidth="1px"
      borderColor="border.subtle"
      rounded="lg"
      overflow="hidden"
    >
      {loadState === 'error' && (
        <Center position="absolute" inset={0} zIndex={1} bg="white" px={6}>
          <Text color="fg.error" textAlign="center">
            {errorMessage ?? 'Failed to load floor plan'}
          </Text>
        </Center>
      )}

      <Stack
        position="absolute"
        top={3}
        left={3}
        zIndex={2}
        gap={2}
        align="flex-start"
        pointerEvents="none"
        maxW={{ base: 'calc(100% - 160px)', md: '280px' }}
      >
        <SceneControlPanel
          loadState={loadState}
          showGridAxes={showGridAxes}
          onShowGridAxesChange={setShowGridAxes}
          showDropPoint={showDropPoint}
          onShowDropPointChange={setShowDropPoint}
          showRoofSlice={showRoofSlice}
          onShowRoofSliceChange={setShowRoofSlice}
          roofSliceHeight={roofSliceHeight}
          onRoofSliceHeightChange={setRoofSliceHeight}
        />

        {showDropPoint && (
          <DropPointPanel
            dropPoint={dropPoint}
            setDropPoint={setDropPoint}
            sceneDebug={sceneDebug}
          />
        )}

        {showGridAxes && sceneDebug && (
          <Card.Root
            size="sm"
            variant="outline"
            bg="bg/90"
            backdropFilter="blur(4px)"
            pointerEvents="auto"
            w="full"
          >
            <Card.Body gap={2} py={3}>
              <Text fontSize="sm" fontWeight="semibold">
                Floor reference
              </Text>

              <Text fontSize="sm" color="fg.muted">
                Floor Z height:{' '}
                <Text as="span" fontFamily="mono" color="fg">
                  {formatCoord(sceneDebug.floorZ)}
                </Text>
              </Text>

              <Text fontSize="xs" color="fg.muted" lineHeight="short">
                Red = +X, green = +Y, blue = +Z. Read vertex positions from the
                grid; bounds min Z is the floor level.
              </Text>

              <Stack gap={0.5} fontFamily="mono" fontSize="xs" color="fg.muted">
                <Text>
                  min ({formatCoord(sceneDebug.min.x)},{' '}
                  {formatCoord(sceneDebug.min.y)},{' '}
                  {formatCoord(sceneDebug.min.z)})
                </Text>

                <Text>
                  max ({formatCoord(sceneDebug.max.x)},{' '}
                  {formatCoord(sceneDebug.max.y)},{' '}
                  {formatCoord(sceneDebug.max.z)})
                </Text>
              </Stack>
            </Card.Body>
          </Card.Root>
        )}
      </Stack>

      <RobotStatusPanel robots={robotStatuses} />

      <HStack
        position="absolute"
        bottom={3}
        left={3}
        zIndex={2}
        gap={2}
        align="center"
        pointerEvents="none"
      >
        <Tooltip content="Reset orbit origin" showArrow>
          <IconButton
            aria-label="Reset orbit origin"
            size="sm"
            variant="surface"
            colorPalette="gray"
            pointerEvents="auto"
            disabled={loadState !== 'ready'}
            onClick={() => resetOrbitRef.current?.()}
            css={{
              _icon: {
                width: '18px',
                height: '18px',
              },
            }}
          >
            <LuLocateFixed />
          </IconButton>
        </Tooltip>

        <Tooltip content="Reset all robots" showArrow>
          <Button
            size="sm"
            variant="surface"
            colorPalette="blue"
            pointerEvents="auto"
            disabled={loadState !== 'ready' || robotStatuses.length === 0}
            onClick={() => resetRobotsRef.current?.()}
          >
            Reset robots
          </Button>
        </Tooltip>

        <Box
          px={2.5}
          py={1.5}
          rounded="md"
          bg="bg/80"
          borderWidth="1px"
          borderColor="border.subtle"
          backdropFilter="blur(4px)"
        >
          <Text fontSize="xs" color="fg.muted">
            Hold <Kbd size="sm">Shift</Kbd> to pan
          </Text>
        </Box>
      </HStack>
    </Box>
  );
}

export default SceneViewer;
