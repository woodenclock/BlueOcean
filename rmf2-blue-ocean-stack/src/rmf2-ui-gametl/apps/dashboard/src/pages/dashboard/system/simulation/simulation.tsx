import { useState, useEffect } from 'react';
import { Box, Grid, SimpleGrid, Icon } from '@chakra-ui/react';
import { toaster } from '@/components/ui/toaster';
import { Banner } from '@/components/banner';
import { MiniStatisticsCard } from '@/components/card';
import { IconBox } from '@/components/icons';
import { OnboardCard } from './components/onboard-card';
import { InitializeCard } from './components/initialize-card';
import { GiRobotGolem } from 'react-icons/gi';
import { MdForklift } from 'react-icons/md';
import { RiRobot2Line } from 'react-icons/ri';
import { DeviceTable } from './components/device-table';
import { ServiceTable } from './components/service-table';
import { serviceInfo } from './variables/service-info';
import type { StateMessage } from './components/state-message';
import { LauncherConfig, BrokerNGSILDConfig } from '@/clients';

type RowObj = {
  robotName: string;
  status: string;
  poseX: number;
  poseY: number;
};
type InitializationState = 'disabled' | 'pending' | 'initialized';

export function Simulation() {
  const [simStarted, setSimStarted] = useState(
    () => localStorage.getItem('isSimStarted') === 'true',
  );

  const [deviceOnboard, setDeviceOnboard] = useState(
    () => localStorage.getItem('isDeviceOnboarded') === 'true',
  );

  const [serviceOnboard, setServiceOnboard] = useState(
    () => localStorage.getItem('isServiceOnboarded') === 'true',
  );

  const [initializeSystemState, setInitializeSystemState] =
    useState<InitializationState>(() => {
      const stateStorage = localStorage.getItem('initializeSystemState');
      if (
        stateStorage === 'disabled' ||
        stateStorage === 'pending' ||
        stateStorage === 'initialized'
      ) {
        return stateStorage;
      } else {
        return 'disabled';
      }
    });

  const [totalMir, setTotalMir] = useState(0);
  const [totalAMR, setTotalAMR] = useState(0);
  // const [totalAGF, setTotalAGF] = useState(0);

  const stopSim = async () => {
    console.debug('Stop Simulation button clicked.');
    toaster.create({
      title: 'Stop Simulation',
      description: `Stop Simulation succesfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });
    setSimStarted(false); // Re-enable Start Simulation button
    localStorage.setItem('isSimStarted', 'false');

    try {
      const response = await fetch(LauncherConfig.BASE + '/stop_sim', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Task stopped:', result);
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const startSim = async () => {
    console.debug('Start Simulation button clicked.');
    toaster.create({
      title: 'Simulation Started',
      description: `Simulation started successfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });
    setSimStarted(true);
    localStorage.setItem('isSimStarted', 'true');

    try {
      const response = await fetch(LauncherConfig.BASE + '/start_sim', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Simulation started:', result);
    } catch (error) {
      console.error('Failed to start simulation:', error);
    }
  };

  const fetchMir = async () => {
    try {
      const response = await fetch(
        BrokerNGSILDConfig.BASE + '/v1/entities?type=StateMessage',
      );
      const StateMessageStats = await response.json();
      setTotalMir(StateMessageStats.length);
      //console.log('API Call Response:', StateMessageStats.length);
    } catch (error) {
      console.error('Error making API call:', error);
    }
  };

  const fetchAMR = async () => {
    try {
      const response = await fetch(
        BrokerNGSILDConfig.BASE + '/v1/entities?type=StateMessage2',
      );
      const StateMessage2Stats = await response.json();
      const transformedData2: RowObj[] = StateMessage2Stats.map(
        (item: StateMessage) => ({
          robotName: item.id.replace(/^urn:ngsi-ld:StateMessage:/, ''),
          status: item.status?.value || '',
          poseX: item.pose?.value?.point2D?.x || 0,
          poseY: item.pose?.value?.point2D?.y || 0,
        }),
      );
      const filtered = transformedData2.filter(
        (item) => item.robotName !== 'agf',
      );
      setTotalAMR(StateMessage2Stats.length);
      console.debug('API Call Response:', filtered);
    } catch (error) {
      console.error('Error making API call:', error);
    }
  };

  const onOnboardDevice = async () => {
    console.debug('Onboard Device...');
    setDeviceOnboard(true);
    localStorage.setItem('isDeviceOnboarded', 'true');
    toaster.create({
      title: 'Device Onboarded',
      description: `Onboarded Devices successfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });

    try {
      const response = await fetch(LauncherConfig.BASE + '/device_onboard', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Device Onboard task sent:', result);
    } catch (error) {
      console.error('Failed to onboard device:', error);
    }
  };

  const onOffboardDevice = async () => {
    console.debug('Offboard Device...');
    setDeviceOnboard(false);
    localStorage.setItem('isDeviceOnboarded', 'false');

    toaster.create({
      title: 'Device Offboarded',
      description: `Offboarded Devices successfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });

    try {
      const response = await fetch(LauncherConfig.BASE + '/device_offboard', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Device Offboard task sent:', result);
    } catch (error) {
      console.error('Failed to offboard device:', error);
    }
  };

  const onOnboardService = async () => {
    console.debug('Onboard Service...');
    setServiceOnboard(true);
    localStorage.setItem('isServiceOnboarded', 'true');
    toaster.create({
      title: 'Service Onboarded',
      description: `Onboarded Service successfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });

    try {
      const response = await fetch(LauncherConfig.BASE + '/service_onboard', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Service Onboard task sent:', result);
    } catch (error) {
      console.error('Failed to onboard service:', error);
    }
  };

  const onOffboardService = async () => {
    console.debug('Offboard Service...');
    setServiceOnboard(false);
    localStorage.setItem('isServiceOnboarded', 'false');

    toaster.create({
      title: 'Service Offboarded',
      description: `Offboarded Services successfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });

    try {
      const response = await fetch(LauncherConfig.BASE + '/service_offboard', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Service Offboard task sent:', result);
    } catch (error) {
      console.error('Failed to offboard service:', error);
    }
  };

  const onInitializeSystem = async () => {
    console.debug('Initializing System...');
    setInitializeSystemState('initialized');
    localStorage.setItem('initializeSystemState', 'initialized');

    toaster.create({
      title: 'Initialize System',
      description: `System Initialized successfully`,
      type: 'success',
      duration: 5000,
      closable: true,
    });

    try {
      const response = await fetch(LauncherConfig.BASE + '/init_system', {
        method: 'POST',
        headers: {
          Accept: '*/*',
        },
      });

      const result = await response.text();
      console.debug('Initialize System Task sent:', result);
    } catch (error) {
      console.error('Failed to send initialize system task:', error);
    }
  };

  useEffect(() => {
    if (deviceOnboard) {
      fetchMir();
      fetchAMR();
    }
  }, [deviceOnboard]);

  useEffect(() => {
    let newState: InitializationState | undefined = undefined;
    if (
      deviceOnboard &&
      serviceOnboard &&
      initializeSystemState === 'disabled'
    ) {
      newState = 'pending';
    }

    if (!deviceOnboard || !serviceOnboard) {
      newState = 'disabled';
    }

    if (newState === undefined) {
      return;
    }

    setInitializeSystemState(newState);
    localStorage.setItem('initializeSystemState', 'pending');
  }, [deviceOnboard, serviceOnboard, initializeSystemState]);

  const brandColor = { base: 'brand.500', _dark: 'white' };
  const boxBg = { base: 'secondaryGray.300', _dark: 'whiteAlpha.100' };

  const initializeMessage = (state: InitializationState) => {
    if (state === 'initialized') {
      return 'System succesfully initialized';
    }
    if (state === 'pending') {
      return 'System is ready to be initialized';
    }
    return 'Onboard Devices and Services to start initialization';
  };

  return (
    <Box>
      <Banner.Root
        bgGradient="to-b"
        gradientFrom="brand.800"
        gradientTo="brand.100"
      >
        <Banner.Header>
          Step into the Creative World of Simulation
        </Banner.Header>
        <Banner.Content>
          <Banner.Button
            borderRadius="5px"
            onClick={startSim}
            disabled={simStarted}
            bg="white"
            _hover={{ bg: 'whiteAlpha.800' }}
          >
            Start Simulation
          </Banner.Button>
          <Banner.Button
            borderRadius="5px"
            onClick={stopSim}
            disabled={!simStarted}
            bg="white"
            _hover={{ bg: 'whiteAlpha.800' }}
          >
            Stop Simulation
          </Banner.Button>
        </Banner.Content>
      </Banner.Root>
      <Grid
        gap={{ base: '20px', xl: '20px' }}
        display={{ base: 'block', lg: 'grid' }}
      ></Grid>

      <SimpleGrid
        columns={{ base: 2, sm: 2, md: 3, lg: 4, '2xl': 5 }}
        gap="20px"
        mt="20px"
      >
        <MiniStatisticsCard
          startContent={
            <IconBox
              w="56px"
              h="56px"
              bg={boxBg}
              icon={
                <Icon w="32px" h="32px" as={RiRobot2Line} color={brandColor} />
              }
            />
          }
          name="Total MIR"
          value={totalMir}
        />
        <MiniStatisticsCard
          startContent={
            <IconBox
              w="56px"
              h="56px"
              bg={boxBg}
              icon={
                <Icon w="32px" h="32px" as={GiRobotGolem} color={brandColor} />
              }
            />
          }
          name="Total Large AMR"
          value={totalAMR}
        />
        <MiniStatisticsCard
          startContent={
            <IconBox
              w="56px"
              h="56px"
              bg={boxBg}
              icon={
                <Icon w="32px" h="32px" as={MdForklift} color={brandColor} />
              }
            />
          }
          name="Total AGF"
          value={totalAMR}
        />
        <MiniStatisticsCard
          startContent={
            <IconBox
              w="56px"
              h="56px"
              bg={boxBg}
              icon={
                <Icon w="32px" h="32px" as={RiRobot2Line} color={brandColor} />
              }
            />
          }
          name="Total Arm"
          value="12"
        />
        <MiniStatisticsCard
          startContent={
            <IconBox
              w="56px"
              h="56px"
              bg={boxBg}
              icon={
                <Icon w="32px" h="32px" as={GiRobotGolem} color={brandColor} />
              }
            />
          }
          name="Total SNS"
          value="9"
        />
      </SimpleGrid>
      <Grid
        pt={{ base: '20px', md: '20px', xl: '20px' }}
        gridTemplateColumns={{ base: '1fr ', lg: '1fr ' }}
        gap={{ base: '20px', xl: '20px' }}
        display={{ base: 'block', lg: 'grid' }}
      >
        <InitializeCard
          mb="10px"
          title="Initialize System"
          description={initializeMessage(initializeSystemState)}
          initializeType="System"
          value={initializeSystemState}
          onInitialize={onInitializeSystem}
        />
      </Grid>
      <Grid
        pt={{ base: '20px', md: '20px', xl: '20px' }}
        gridTemplateColumns={{ base: '1fr 1fr ', lg: '1fr 1fr ' }}
        gap={{ base: '20px', xl: '20px' }}
        display={{ base: 'block', '2xl': 'grid' }}
      >
        <Grid>
          <OnboardCard
            mb="10px"
            title="Device Onboarding"
            description="Monitor and Track all your devices"
            onboardType="Device"
            isOnboard={deviceOnboard}
            onOnboard={onOnboardDevice}
            onOffboard={onOffboardDevice}
          />
        </Grid>

        <Grid>
          <OnboardCard
            mb="10px"
            title="Service Onboarding"
            description="Monitor health of RMF services"
            onboardType="Service"
            isOnboard={serviceOnboard}
            onOnboard={onOnboardService}
            onOffboard={onOffboardService}
          />
        </Grid>
      </Grid>

      <Grid
        pt={{ base: '20px', md: '20px', xl: '20px' }}
        gridTemplateColumns={{ base: '1fr 1fr ', lg: '1fr 1fr ' }}
        gap={{ base: '20px', xl: '20px' }}
        display={{ base: 'block', lg: 'grid' }}
      >
        {deviceOnboard && <DeviceTable />}
        {serviceOnboard && <ServiceTable serviceInfo={serviceInfo} />}
      </Grid>
    </Box>
  );
}

export default Simulation;
