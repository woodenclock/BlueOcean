import { Box, Flex, Icon, Text } from '@chakra-ui/react';
// Custom components
import { Horizon } from '@rmf2-ui/chakra';
// Assets
import { IoWifi } from 'react-icons/io5'; // Online and Offline icons
import { FiWifiOff } from 'react-icons/fi';

import Card = Horizon.Card;
import CardProps = Horizon.CardProps;

export interface NetworkStatusCardProps extends CardProps {
  name: string;
  description: string;
  isOnline: boolean; // Accept isOnline as a prop
}

export function NetworkStatusCard(props: NetworkStatusCardProps) {
  const { name, description, isOnline, ...rest } = props;
  const textColor = { base: 'navy.700', _dark: 'white' };

  // Determine the icon color and the icon based on the isOnline prop
  const iconColor = isOnline ? 'green.500' : 'red.500'; // Green for online, red for offline
  const icon = isOnline ? IoWifi : FiWifiOff; // Use different icons for online/offline

  return (
    <Card p="20px" {...rest}>
      <Flex direction={{ base: 'column' }} justify="center" align="center">
        <Box mb={{ base: '20px', '2xl': '20px' }} position="relative">
          <Flex justify="center" align="center">
            <Icon
              as={icon} // Dynamically change the icon based on online/offline status
              w="100px"
              h="100px"
              color={iconColor} // Change the icon color based on the status
            />
          </Flex>
        </Box>
        <Flex
          flexDirection="column"
          justify="space-between"
          h="100%"
          align="center"
        >
          <Flex mb="auto" align="center">
            <Flex direction="column" align="center">
              <Text
                color={textColor}
                fontSize={{
                  base: 'xl',
                  md: 'lg',
                  lg: 'lg',
                  xl: 'lg',
                  '2xl': 'md',
                }}
                mb="5px"
                fontWeight="bold"
                textAlign="center"
              >
                {name}
              </Text>
              <Text
                color="secondaryGray.600"
                fontSize={{ base: 'sm' }}
                fontWeight="400"
                textAlign="center"
              >
                {description}
              </Text>
            </Flex>
          </Flex>
        </Flex>
      </Flex>
    </Card>
  );
}

export default NetworkStatusCard;
