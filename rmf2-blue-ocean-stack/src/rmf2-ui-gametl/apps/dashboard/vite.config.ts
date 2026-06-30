import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

// https://vite.dev/config/
export default defineConfig({
  server: {
    host: true,
    port: Number(process.env.UI_PORT) || 3000,
  },
  plugins: [react(), tsconfigPaths()],
});
