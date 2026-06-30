import { RTSAPI } from '@rmf2-ui/client';

export const RTSClientOptions: RTSAPI.ClientOptions = {
  baseUrl: import.meta.env.VITE_RTS_BASE,
};

export function useRTSClient() {
  const client = new RTSAPI.Client(RTSClientOptions);
  return client;
}
