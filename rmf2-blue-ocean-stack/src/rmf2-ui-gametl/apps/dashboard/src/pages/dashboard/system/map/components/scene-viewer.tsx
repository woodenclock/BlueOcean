import { useEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  Card,
  Center,
  Field,
  HStack,
  IconButton,
  Input,
  Kbd,
  Stack,
  Switch,
  Text,
} from '@chakra-ui/react';
import { LuLocateFixed, LuRotateCcw } from 'react-icons/lu';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { ViewportGizmo } from 'three-viewport-gizmo';
import { Tooltip } from '@/components/ui/tooltip';
import { DropPointMarker } from '../drop-point-marker';
import { NavigationOverlay } from '../navigation-overlay';

const SCENE_URL = '/RMF2_SIM/Test_3.glb';

// const SCENE_URL = '/scene.draco.glb';
const DRACO_DECODER_PATH =
  'https://www.gstatic.com/draco/versioned/decoders/1.5.6/';
const INTRO_DURATION_MS = 500;
const INTRO_START_DISTANCE_FACTOR = 1.5;
const END_DISTANCE_FACTOR = 0.75;
// Scene is Z-up (robotics convention): +Z is vertical, floor lies in the XY plane.
// END_VIEW_ANGLE is measured from +Z (vertical) toward -Y (the camera's horizontal
// offset), so 45° gives an isometric-style angled look from above.
const END_VIEW_ANGLE = Math.PI / 4;

type LoadState = 'loading' | 'ready' | 'error';

type CameraFrame = {
  center: THREE.Vector3;
  maxDim: number;
  sphereRadius: number;
  startPosition: THREE.Vector3;
  endPosition: THREE.Vector3;
};

type SceneBounds = {
  min: THREE.Vector3;
  max: THREE.Vector3;
  maxDim: number;
  floorZ: number;
};

type SceneDebugInfo = {
  floorZ: number;
  min: { x: number; y: number; z: number };
  max: { x: number; y: number; z: number };
};

type DropPointCoords = { x: number; y: number; z: number };

type SceneViewerApi = {
  setShowGridAxes: (show: boolean) => void;
  setNavigationEnabled: (enabled: boolean) => void;
  setDropPointEnabled: (enabled: boolean) => void;
  setDropPointPosition: (position: DropPointCoords) => void;
};

function easeInOutCubic(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

function tuneMaterials(root: THREE.Object3D) {
  root.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;

    const materials = Array.isArray(child.material)
      ? child.material
      : [child.material];

    for (const material of materials) {
      // Coplanar faces in architectural exports often z-fight at grazing angles.
      material.polygonOffset = true;
      material.polygonOffsetFactor = 1;
      material.polygonOffsetUnits = 1;

      if (material.transparent || material.opacity < 1) {
        material.depthWrite = false;
        material.side = THREE.FrontSide;
        child.renderOrder = 1;
      } else if (material.side === THREE.DoubleSide) {
        // Back faces fighting with front faces on thin geometry.
        material.side = THREE.FrontSide;
      }
    }
  });
}

function computeSceneBounds(root: THREE.Object3D): SceneBounds {
  const box = new THREE.Box3().setFromObject(root);
  const min = box.min.clone();
  const max = box.max.clone();
  const size = box.getSize(new THREE.Vector3());

  return {
    min,
    max,
    maxDim: Math.max(size.x, size.y, size.z),
    floorZ: min.z,
  };
}

function toSceneDebugInfo(bounds: SceneBounds): SceneDebugInfo {
  return {
    floorZ: bounds.floorZ,
    min: { x: bounds.min.x, y: bounds.min.y, z: bounds.min.z },
    max: { x: bounds.max.x, y: bounds.max.y, z: bounds.max.z },
  };
}

function formatCoord(value: number) {
  return value.toFixed(3);
}

function createGridAxesHelpers(bounds: SceneBounds) {
  const size = bounds.max.clone().sub(bounds.min);
  // Z-up: floor is the XY plane, so the grid extent should span X and Y.
  const gridExtent = Math.max(size.x, size.y) * 1.25;
  const divisions = Math.max(10, Math.round(gridExtent / 2));

  const grid = new THREE.GridHelper(gridExtent, divisions, 0x888888, 0xcccccc);
  // GridHelper is authored in the XZ plane; rotate it into XY for a Z-up scene.
  grid.rotation.x = Math.PI / 2;
  const axes = new THREE.AxesHelper(bounds.maxDim * 0.35);

  const group = new THREE.Group();
  group.add(grid, axes);
  group.position.set(
    (bounds.min.x + bounds.max.x) / 2,
    (bounds.min.y + bounds.max.y) / 2,
    bounds.floorZ,
  );
  group.visible = false;

  return group;
}

function disposeObject3D(root: THREE.Object3D) {
  root.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose();
      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material];
      materials.forEach((material) => material.dispose());
    } else if (child instanceof THREE.LineSegments) {
      child.geometry.dispose();
      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

function computeCameraFrame(root: THREE.Object3D): CameraFrame {
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const sphere = box.getBoundingSphere(new THREE.Sphere());

  const startDistance = maxDim * INTRO_START_DISTANCE_FACTOR;
  const endDistance = maxDim * END_DISTANCE_FACTOR;

  // Z-up: intro starts straight overhead (high +Z) and ends at an angled view
  // offset along -Y so that +Y projects "up" on screen.
  return {
    center,
    maxDim,
    sphereRadius: sphere.radius,
    startPosition: new THREE.Vector3(
      center.x,
      center.y,
      center.z + startDistance,
    ),
    endPosition: new THREE.Vector3(
      center.x,
      center.y - endDistance * Math.sin(END_VIEW_ANGLE),
      center.z + endDistance * Math.cos(END_VIEW_ANGLE),
    ),
  };
}

function applyCameraFrame(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  frame: CameraFrame,
  position: THREE.Vector3,
) {
  // Tight near/far improves depth precision and reduces z-fighting.
  camera.near = Math.max(frame.sphereRadius / 500, 0.05);
  camera.far = frame.sphereRadius * 20;
  camera.updateProjectionMatrix();

  controls.target.copy(frame.center);
  controls.minDistance = frame.maxDim * 0.15;
  controls.maxDistance = frame.maxDim * 4;
  camera.position.copy(position);
  camera.lookAt(frame.center);
  controls.update();
}

function frameCamera(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  root: THREE.Object3D,
) {
  const frame = computeCameraFrame(root);
  applyCameraFrame(camera, controls, frame, frame.endPosition);
}

function animateIntroCamera(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  frame: CameraFrame,
  isDisposed: () => boolean,
) {
  applyCameraFrame(camera, controls, frame, frame.startPosition);

  const startTime = performance.now();
  const from = frame.startPosition.clone();

  const tick = (now: number) => {
    if (isDisposed()) return;

    const t = Math.min((now - startTime) / INTRO_DURATION_MS, 1);
    const eased = easeInOutCubic(t);

    camera.position.lerpVectors(from, frame.endPosition, eased);
    camera.lookAt(frame.center);
    controls.update();

    if (t < 1) {
      requestAnimationFrame(tick);
    } else {
      applyCameraFrame(camera, controls, frame, frame.endPosition);
    }
  };

  requestAnimationFrame(tick);
}

export function SceneViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const resetOrbitRef = useRef<(() => void) | null>(null);
  const resetPathRef = useRef<(() => void) | null>(null);
  const sceneApiRef = useRef<SceneViewerApi | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showGridAxes, setShowGridAxes] = useState(false);
  const [showNavigation, setShowNavigation] = useState(true);
  const [showDropPoint, setShowDropPoint] = useState(false);
  const [dropPoint, setDropPoint] = useState<DropPointCoords>({
    x: 0,
    y: 0,
    z: 0,
  });
  const [sceneDebug, setSceneDebug] = useState<SceneDebugInfo | null>(null);
  const showNavigationRef = useRef(showNavigation);
  const showDropPointRef = useRef(showDropPoint);
  const dropPointRef = useRef(dropPoint);

  showNavigationRef.current = showNavigation;
  showDropPointRef.current = showDropPoint;
  dropPointRef.current = dropPoint;

  useEffect(() => {
    sceneApiRef.current?.setShowGridAxes(showGridAxes);
  }, [showGridAxes, sceneDebug]);

  useEffect(() => {
    sceneApiRef.current?.setNavigationEnabled(showNavigation);
  }, [showNavigation, loadState]);

  useEffect(() => {
    sceneApiRef.current?.setDropPointEnabled(showDropPoint);
  }, [showDropPoint, loadState]);

  useEffect(() => {
    sceneApiRef.current?.setDropPointPosition(dropPoint);
  }, [dropPoint, loadState]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
    // Z-up scene: orbit controls, gizmo, and projection all treat +Z as vertical.
    const previousDefaultUp = THREE.Object3D.DEFAULT_UP.clone();
    THREE.Object3D.DEFAULT_UP.set(0, 0, 1);
    camera.up.set(0, 0, 1);
    camera.position.set(5, -5, 5);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      logarithmicDepthBuffer: true,
      powerPreference: 'high-performance',
    });
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

    const gizmo = new ViewportGizmo(camera, renderer, {
      container: renderer.domElement.parentElement ?? container,
    });
    gizmo.attachControls(controls);
    controls.zoomSpeed = 2.5;

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath(DRACO_DECODER_PATH);

    const loader = new GLTFLoader();
    loader.setDRACOLoader(dracoLoader);

    let animationFrameId = 0;
    let disposed = false;
    let loadedScene: THREE.Group | null = null;
    let gridAxesHelpers: THREE.Group | null = null;
    let navigationOverlay: NavigationOverlay | null = null;
    let dropPointMarker: DropPointMarker | null = null;
    const pickRaycaster = new THREE.Raycaster();
    const pickPointer = new THREE.Vector2();

    const onDropPointPointerDown = (event: PointerEvent) => {
      if (!showDropPointRef.current || !event.altKey || !dropPointMarker)
        return;

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
      controls.update();
      navigationOverlay?.tick(clock.getDelta());
      renderer.render(scene, camera);
      gizmo.render();
    };
    animate();

    loader.load(
      SCENE_URL,
      async (gltf) => {
        if (disposed) return;

        loadedScene = gltf.scene;
        // GLTF is Y-up by spec; rotate to Z-up world convention (+Z vertical).
        gltf.scene.rotation.x = Math.PI / 2;
        tuneMaterials(gltf.scene);
        scene.add(gltf.scene);

        const bounds = computeSceneBounds(gltf.scene);
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
            if (gridAxesHelpers) gridAxesHelpers.visible = show;
          },
          setNavigationEnabled(enabled) {
            navigationOverlay?.setEnabled(enabled);
          },
          setDropPointEnabled(enabled) {
            dropPointMarker?.setVisible(enabled);
          },
          setDropPointPosition(position) {
            dropPointMarker?.setPosition(position);
          },
        };

        setSceneDebug(toSceneDebugInfo(bounds));

        const frame = computeCameraFrame(gltf.scene);
        resetOrbitRef.current = () => {
          frameCamera(camera, controls, gltf.scene);
        };

        try {
          navigationOverlay = await NavigationOverlay.create({
            scene,
            domElement: renderer.domElement,
            camera,
            pathUrl: '/navigation-path.json',
          });
          // Match the GLTF Y-up → Z-up rotation applied to the floorplan.
          navigationOverlay.group.rotation.x = Math.PI / 2;
          navigationOverlay.on('waypoint:selected', ({ waypointId }) => {
            console.info('[navigation] waypoint:selected', waypointId);
          });
          navigationOverlay.on('robot:arrived', ({ goalId }) => {
            console.info('[navigation] robot:arrived', goalId);
          });
          navigationOverlay.setEnabled(showNavigationRef.current);
          resetPathRef.current = () => {
            if (navigationOverlay?.isEnabled()) navigationOverlay.reset();
          };
        } catch (overlayError) {
          console.error('Navigation overlay failed to load', overlayError);
        }

        if (disposed) {
          navigationOverlay?.dispose();
          navigationOverlay = null;
          return;
        }

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
      resetPathRef.current = null;
      sceneApiRef.current = null;

      navigationOverlay?.dispose();
      navigationOverlay = null;

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
        <Box
          px={2.5}
          py={2}
          rounded="md"
          bg="bg/90"
          borderWidth="1px"
          borderColor="border.subtle"
          backdropFilter="blur(4px)"
          pointerEvents="auto"
        >
          <Stack gap={2}>
            <Switch.Root
              size="sm"
              colorPalette="blue"
              checked={showGridAxes}
              disabled={loadState !== 'ready'}
              onCheckedChange={(details) => setShowGridAxes(details.checked)}
            >
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
              <Switch.Label fontSize="sm">Grid &amp; axes</Switch.Label>
            </Switch.Root>
            <Switch.Root
              size="sm"
              colorPalette="purple"
              checked={showNavigation}
              disabled={loadState !== 'ready'}
              onCheckedChange={(details) => setShowNavigation(details.checked)}
            >
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
              <Switch.Label fontSize="sm">Robot navigation</Switch.Label>
            </Switch.Root>
            <Switch.Root
              size="sm"
              colorPalette="yellow"
              checked={showDropPoint}
              disabled={loadState !== 'ready'}
              onCheckedChange={(details) => setShowDropPoint(details.checked)}
            >
              <Switch.HiddenInput />
              <Switch.Control>
                <Switch.Thumb />
              </Switch.Control>
              <Switch.Label fontSize="sm">Drop point</Switch.Label>
            </Switch.Root>
          </Stack>
        </Box>
        {showDropPoint && (
          <Card.Root
            size="sm"
            variant="outline"
            bg="bg/90"
            backdropFilter="blur(4px)"
            pointerEvents="auto"
            w="full"
          >
            <Card.Body gap={3} py={3}>
              <Text fontSize="sm" fontWeight="semibold">
                Drop point
              </Text>
              <Text fontSize="xs" color="fg.muted" lineHeight="short">
                Same world X, Y, Z as navigation-path.json (blue axis = Z up).
                Alt+click sets X and Y on the plane at the current Z.
              </Text>
              <Stack gap={2}>
                {(['x', 'y', 'z'] as const).map((axis) => (
                  <Field.Root key={axis}>
                    <Field.Label fontSize="xs" textTransform="uppercase">
                      {axis}
                    </Field.Label>
                    <Input
                      size="sm"
                      type="number"
                      step="0.1"
                      fontFamily="mono"
                      value={dropPoint[axis]}
                      onChange={(e) => {
                        const value = Number.parseFloat(e.target.value);
                        if (Number.isNaN(value)) return;
                        setDropPoint((prev) => ({ ...prev, [axis]: value }));
                      }}
                    />
                  </Field.Root>
                ))}
              </Stack>
              {sceneDebug && (
                <Button
                  size="xs"
                  variant="outline"
                  colorPalette="gray"
                  onClick={() =>
                    setDropPoint((prev) => ({
                      ...prev,
                      z: sceneDebug.floorZ,
                    }))
                  }
                >
                  Snap Z to floor ({formatCoord(sceneDebug.floorZ)})
                </Button>
              )}
              <Box
                px={2}
                py={1.5}
                rounded="md"
                bg="bg.subtle"
                borderWidth="1px"
                borderColor="border.subtle"
                fontFamily="mono"
                fontSize="xs"
                color="fg.muted"
                wordBreak="break-all"
              >
                {`"x": ${formatCoord(dropPoint.x)}, "y": ${formatCoord(dropPoint.y)}, "z": ${formatCoord(dropPoint.z)}`}
              </Box>
            </Card.Body>
          </Card.Root>
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
        <Tooltip content="Restart path" showArrow>
          <IconButton
            aria-label="Restart path"
            size="sm"
            variant="surface"
            colorPalette="purple"
            pointerEvents="auto"
            disabled={loadState !== 'ready' || !showNavigation}
            onClick={() => resetPathRef.current?.()}
            css={{
              _icon: {
                width: '18px',
                height: '18px',
              },
            }}
          >
            <LuRotateCcw />
          </IconButton>
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
