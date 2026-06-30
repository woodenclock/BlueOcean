// Master-frame map image metadata from the VDA5050 master (/map/image/meta).
// Returns null when the master serves no image (e.g. dry-run -> 404), so the
// visualiser simply skips the backdrop.
import { useEffect, useState } from 'react';
import { BrokerStatusConfig } from '@/clients';

import type { MapImageMeta } from './types';

const BASE = BrokerStatusConfig.BASE ?? 'http://localhost:8000';

export function useMapImage(): MapImageMeta | null {
  const [meta, setMeta] = useState<MapImageMeta | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${BASE}/map/image/meta`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setMeta({
          url: `${BASE}${data.url ?? '/map/image'}`,
          resolution: data.resolution,
          origin: [data.origin[0], data.origin[1]],
          width: data.width,
          height: data.height,
        });
      })
      .catch(() => {
        /* no image available — leave backdrop empty */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return meta;
}
