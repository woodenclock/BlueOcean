import { OpenAPIConfig } from './openapi';

// Blue Ocean scheduler (FastAPI, port 8089) — exposes the /demo/* endpoints.
// Reuses VITE_RTS_BASE; the generated RTS client doesn't cover the demo routes,
// so callers hit these with plain fetch.
export const SchedulerConfig: OpenAPIConfig = {
  BASE: import.meta.env.VITE_RTS_BASE,
};
