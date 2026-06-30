// Live map + AGV state from the VDA5050 master over a WebSocket, with retry.
import { useEffect, useRef, useState } from 'react';
import { BrokerStatusConfig } from '@/clients';

import type { AgvState, MapData, SocketStatus } from './types';

const WS_URL =
  (BrokerStatusConfig.BASE ?? 'http://localhost:8000').replace(/^http/, 'ws') +
  '/ws/state';

export function useVdaState() {
  const [map, setMap] = useState<MapData | null>(null);
  const [agvs, setAgvs] = useState<AgvState[]>([]);
  const [status, setStatus] = useState<SocketStatus>('connecting');
  const retryRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    let socket: WebSocket;
    let closed = false;

    const connect = () => {
      setStatus('connecting');
      socket = new WebSocket(WS_URL);
      socket.onopen = () => setStatus('connected');
      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'map') {
          setMap({
            nodes: msg.nodes ?? [],
            edges: msg.edges ?? [],
            stations: msg.stations ?? [],
          });
        } else if (msg.type === 'state') {
          setAgvs(msg.agvs ?? []);
        }
      };
      socket.onclose = () => {
        setStatus('disconnected');
        if (!closed) {
          retryRef.current = setTimeout(connect, 2000);
        }
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(retryRef.current);
      socket.close();
    };
  }, []);

  return { map, agvs, status };
}
