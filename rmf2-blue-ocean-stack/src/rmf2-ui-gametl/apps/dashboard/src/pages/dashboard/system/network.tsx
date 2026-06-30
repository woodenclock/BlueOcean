// Chakra imports
import {
  Badge,
  Box,
  HStack,
  Icon,
  Stack,
  Table,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FiWifiOff } from 'react-icons/fi';
import { IoWifi } from 'react-icons/io5';

// Custom components
import { toaster } from '@/components/ui/toaster';
import { Banner } from '@/components/banner';
import { useState, useEffect } from 'react';
import { LauncherConfig, BrokerStatusConfig } from '@/clients';
import { RTSClientOptions } from '@/clients/rts';

type ServicesStatusKey =
  | 'proxy'
  | 'mongodb'
  | 'redis'
  | 'rabbitmq'
  | 'postgres'
  | 'it_connector'
  | 'swagger'
  | 'event_mgr'
  | 'rmf_proxy'
  | 'rmf_logger'
  | 'test_logger_database'
  | 'rts';

const mockServicesConnected =
  import.meta.env.VITE_NETWORK_MOCK_CONNECTED === 'true';

const ENDPOINT_CONFIGS = {
  broker: {
    base: BrokerStatusConfig.BASE,
    statusPath: '/status',
  },
  rts: {
    base: RTSClientOptions.baseUrl ?? '',
    statusPath: '/status',
  },
} as const;

type EndpointKey = keyof typeof ENDPOINT_CONFIGS;

interface NetworkServiceRow {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly statusKey: ServicesStatusKey;
  readonly endpoint: EndpointKey;
}

const NETWORK_SERVICE_ROWS: readonly NetworkServiceRow[] = [
  {
    id: 'rts',
    name: 'RTS Service',
    description:
      'Real-Time Scheduler service for managing and optimizing task schedules',
    statusKey: 'rts',
    endpoint: 'rts',
  },
  {
    id: 'monitoring',
    name: 'Monitoring Service',
    description: 'Used for monitoring internal IOCS services.',
    statusKey: 'mongodb',
    endpoint: 'broker',
  },
  {
    id: 'proxy',
    name: 'Proxy Service',
    description:
      'Used for forwarding messages to databases, handling routing and message transformation.',
    statusKey: 'proxy',
    endpoint: 'broker',
  },
  {
    id: 'logging',
    name: 'Logging Service',
    description: 'Service for storing data into database',
    statusKey: 'rmf_logger',
    endpoint: 'broker',
  },
  {
    id: 'rabbitmq',
    name: 'RabbitMQ Service',
    description: 'Service bus data broadcasting using exchange ',
    statusKey: 'rabbitmq',
    endpoint: 'broker',
  },
  {
    id: 'postgres',
    name: 'Postgres Service',
    description:
      'Used for Data analytics, NGSI-LD Context broker, IT Connectors Configuration ',
    statusKey: 'postgres',
    endpoint: 'broker',
  },
  {
    id: 'data-model-repository',
    name: 'Data Model Repository Service',
    description: 'Internal storage for data model ',
    statusKey: 'redis',
    endpoint: 'broker',
  },
  {
    id: 'it-connector',
    name: 'IT-Connector Service',
    description: 'IT data pipeline from external data source to context broker',
    statusKey: 'it_connector',
    endpoint: 'broker',
  },
  {
    id: 'event-manager',
    name: 'EventManager Service',
    description: 'Processes and managers system event triggers',
    statusKey: 'event_mgr',
    endpoint: 'broker',
  },
];

function parseEndpoint(base: string): { protocol: string; host: string } {
  try {
    const url = new URL(base);
    return {
      protocol: url.protocol.replace(':', '').toUpperCase(),
      host: url.host,
    };
  } catch {
    return { protocol: 'HTTP', host: base };
  }
}

function timeAgoFromMs(timestampMs: number): string {
  const secs = Math.floor((Date.now() - timestampMs) / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function timeAgo(timeNs: number): string {
  return timeAgoFromMs(timeNs / 1_000_000);
}

const defaultServicesStatus = {
  proxy: false,
  mongodb: false,
  redis: false,
  rabbitmq: false,
  postgres: false,
  it_connector: false,
  swagger: false,
  event_mgr: false,
  rmf_proxy: false,
  rmf_logger: false,
  test_logger_database: false,
  rts: false,
};

const devConnectedServicesStatus = {
  proxy: true,
  mongodb: true,
  redis: true,
  rabbitmq: true,
  postgres: true,
  it_connector: true,
  swagger: true,
  event_mgr: true,
  rmf_proxy: true,
  rmf_logger: true,
  test_logger_database: true,
  rts: false,
};

const defaultRtsData = { online: false, timeNs: null as number | null };

const POLL_INTERVAL_MS = 5000;

export function Network() {
  const [isStartIOCSClicked, setisStartIOCSClicked] = useState(false);
  const [, setTick] = useState(0);
  const [servicesStatus, setServicesStatus] = useState(defaultServicesStatus);
  const [brokerLastPolledAt, setBrokerLastPolledAt] = useState<number | null>(
    null,
  );
  const [rtsData, setRtsData] = useState(defaultRtsData);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const storedStartIOCSClicked =
      localStorage.getItem('isIOCSStarted') === 'true';

    if (storedStartIOCSClicked) {
      setisStartIOCSClicked(storedStartIOCSClicked);
    }
  }, []);

  useEffect(() => {
    const fetchBrokerStatus = async () => {
      if (mockServicesConnected) {
        setServicesStatus(devConnectedServicesStatus);
        setBrokerLastPolledAt(Date.now());
        return;
      }

      try {
        const response = await fetch(BrokerStatusConfig.BASE + '/status', {
          method: 'GET',
          headers: { Accept: '*' },
        });
        const data = await response.json();
        setServicesStatus({
          proxy: data.redis.status,
          mongodb: data.mongodb.status,
          redis: data.redis.status,
          rabbitmq: data.rabbitmq.status,
          postgres: data.postgres.status,
          it_connector: data.it_connector.status,
          swagger: data.swagger.status,
          event_mgr: data.event_mgr.status,
          rmf_proxy: data.rmf_proxy.status,
          rmf_logger: data.rmf_logger.status,
          test_logger_database: data['test-logger-database'].status,
          rts: false,
        });
        setBrokerLastPolledAt(Date.now());
      } catch {
        setServicesStatus(defaultServicesStatus);
        setBrokerLastPolledAt(null);
      }
    };

    fetchBrokerStatus();
    const intervalId = setInterval(fetchBrokerStatus, POLL_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    const fetchRtsStatus = async () => {
      try {
        const response = await fetch(
          (RTSClientOptions.baseUrl ?? '') + '/status',
          { method: 'GET', headers: { Accept: '*' } },
        );
        const data = await response.json();
        setRtsData({
          online: data.status === 'ok',
          timeNs: (data.time_ns as number) ?? null,
        });
      } catch {
        setRtsData(defaultRtsData);
      }
    };

    fetchRtsStatus();
    const intervalId = setInterval(fetchRtsStatus, POLL_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, []);

  const allServicesStatus = { ...servicesStatus, rts: rtsData.online };

  const stopIOCS = async () => {
    console.log('Stop Network button clicked.');
    toaster.create({
      title: 'Stop Network',
      description: 'Stopping Network',
      type: 'success',
      duration: 5000,
      closable: true,
    });
    setisStartIOCSClicked(false);
    localStorage.setItem('isIOCSStarted', 'false');

    try {
      const response = await fetch(LauncherConfig.BASE + '/stop_iocs', {
        method: 'POST',
        headers: { Accept: '*' },
      });
      const result = await response.text();
      console.log('Task stopped:', result);
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const startIOCS = async () => {
    console.log('Start Network button clicked.');
    toaster.create({
      title: 'Network Started',
      description: 'Network Starting',
      type: 'success',
      duration: 5000,
      closable: true,
    });
    setisStartIOCSClicked(true);
    localStorage.setItem('isIOCSStarted', 'true');

    try {
      const response = await fetch(LauncherConfig.BASE + '/start_iocs', {
        method: 'POST',
        headers: { Accept: '*' },
      });
      const result = await response.text();
      console.log('Network started:', result);
    } catch (error) {
      console.error('Failed to start network:', error);
    }
  };

  return (
    <Box>
      <Banner.Root>
        <Banner.Header>Unleashing the Power of Connectivity</Banner.Header>
        <Banner.Content>
          <Banner.Button onClick={startIOCS} disabled={isStartIOCSClicked}>
            Start Network
          </Banner.Button>
          <Banner.Button onClick={stopIOCS} disabled={!isStartIOCSClicked}>
            Stop Network
          </Banner.Button>
        </Banner.Content>
      </Banner.Root>

      <Stack gap="5" mt="20px" width="full">
        <Table.ScrollArea maxW="full">
          <Table.Root
            size="sm"
            variant="outline"
            striped
            minW={{ base: '520px', md: 'full' }}
          >
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader minW="168px">Status</Table.ColumnHeader>
                <Table.ColumnHeader minW="180px">Name</Table.ColumnHeader>
                <Table.ColumnHeader>Description</Table.ColumnHeader>
                <Table.ColumnHeader minW="280px">Endpoint</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {NETWORK_SERVICE_ROWS.map((row) => {
                const isOnline = allServicesStatus[row.statusKey];
                const StatusIcon = isOnline ? IoWifi : FiWifiOff;
                const iconColor = isOnline ? 'green.500' : 'red.500';
                const statusLabel = isOnline ? 'Online' : 'Offline';
                const statusColor = isOnline ? 'green.600' : 'red.600';
                const { base, statusPath } = ENDPOINT_CONFIGS[row.endpoint];
                const { protocol, host } = parseEndpoint(base);
                const responsePath =
                  row.endpoint === 'rts'
                    ? rtsData.timeNs !== null
                      ? timeAgo(rtsData.timeNs)
                      : null
                    : isOnline && brokerLastPolledAt !== null
                      ? timeAgoFromMs(brokerLastPolledAt)
                      : null;

                return (
                  <Table.Row key={row.id}>
                    <Table.Cell verticalAlign="middle">
                      <HStack gap="3">
                        <Icon
                          as={StatusIcon}
                          color={iconColor}
                          boxSize="40px"
                          aria-hidden
                        />
                        <Text
                          fontSize="sm"
                          fontWeight="medium"
                          color={statusColor}
                        >
                          {statusLabel}
                        </Text>
                      </HStack>
                    </Table.Cell>
                    <Table.Cell verticalAlign="top">
                      <Text fontWeight="semibold">{row.name}</Text>
                    </Table.Cell>
                    <Table.Cell verticalAlign="top" color="fg.muted">
                      {row.description}
                    </Table.Cell>
                    <Table.Cell verticalAlign="top">
                      <VStack align="start" gap="1">
                        <HStack gap="1" flexWrap="wrap">
                          <Badge
                            colorPalette="blue"
                            size="sm"
                            fontFamily="mono"
                          >
                            GET
                          </Badge>
                          <Badge
                            colorPalette="purple"
                            size="sm"
                            fontFamily="mono"
                          >
                            {protocol}
                          </Badge>
                          <Text
                            fontSize="xs"
                            fontFamily="mono"
                            color="fg.muted"
                          >
                            {host}
                          </Text>
                          <Text
                            fontSize="xs"
                            fontFamily="mono"
                            fontWeight="semibold"
                          >
                            {statusPath}
                          </Text>
                        </HStack>
                        {responsePath !== null && (
                          <Text
                            fontSize="xs"
                            fontFamily="mono"
                            color="fg.subtle"
                          >
                            ↳ {responsePath}
                          </Text>
                        )}
                      </VStack>
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>
      </Stack>
    </Box>
  );
}

export default Network;
