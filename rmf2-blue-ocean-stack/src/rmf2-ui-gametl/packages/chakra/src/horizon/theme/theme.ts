import { createSystem, defineConfig, defaultConfig } from '@chakra-ui/react';
import { globalCss, globalTokens } from './styles';
import { buttonRecipe, inputRecipe } from './recipes';

export const systemConfig = defineConfig({
  theme: {
    tokens: globalTokens,
    recipes: {
      button: buttonRecipe,
      input: inputRecipe,
    },
  },
  globalCss: globalCss,
});

export const system = createSystem(defaultConfig, systemConfig);

export default system;
