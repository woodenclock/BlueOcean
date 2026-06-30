import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig([
  {
    input: 'src/rts/openapi.json', // sign up at app.heyapi.dev
    output: {
      format: 'prettier',
      lint: 'eslint',
      path: 'src/rts/generated',
    },
  },
]);
