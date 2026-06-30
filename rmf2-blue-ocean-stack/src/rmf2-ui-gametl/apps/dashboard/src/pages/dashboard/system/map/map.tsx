// import { SceneViewer } from './components/new-scene-viewer';
// TODO: Refactor to segregate the scene from the rest of the page

import { Center, Spinner } from '@chakra-ui/react';
import { lazy, Suspense } from 'react';

const SceneViewer = lazy(() => import('./components/new-scene-viewer'));
export function Map() {
  return (
    <Suspense
      fallback={
        <Center h="100vh">
          <Spinner />
        </Center>
      }
    >
      <SceneViewer />
    </Suspense>
  );
}

export default Map;
