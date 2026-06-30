import { OpenAPIConfig } from './openapi';

export const BrokerStatusConfig: OpenAPIConfig = {
  BASE: import.meta.env.VITE_BROKER_STATUS_BASE,
};

export const BrokerNGSILDConfig: OpenAPIConfig = {
  BASE: import.meta.env.VITE_BROKER_NGSI_LD_BASE,
};
