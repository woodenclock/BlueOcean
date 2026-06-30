import { createSystem, defineConfig, defaultConfig } from '@chakra-ui/react';
import { Horizon } from '@rmf2-ui/chakra';
import { buttonRecipe } from './recipes';

const customConfig = defineConfig({
  theme: {
    recipes: {
      button: buttonRecipe,
    },
  },
});

export const system = createSystem(
  defaultConfig,
  Horizon.systemConfig,
  customConfig,
);
