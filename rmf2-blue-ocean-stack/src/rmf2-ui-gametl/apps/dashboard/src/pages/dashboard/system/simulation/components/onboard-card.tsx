import { Button, Flex, Text } from '@chakra-ui/react';
import { Horizon } from '@rmf2-ui/chakra';
import { useState, useEffect, MouseEvent, MouseEventHandler } from 'react';
import Card = Horizon.Card;
import CardProps = Horizon.CardProps;

export interface OnboardCardProps extends CardProps {
  title: string;
  description: string;
  onboardType: string;
  isOnboard?: boolean;
  onOnboard?: MouseEventHandler<HTMLButtonElement>;
  onOffboard?: MouseEventHandler<HTMLButtonElement>;
}

export function OnboardCard(props: OnboardCardProps) {
  const {
    title,
    description,
    onboardType,
    isOnboard,
    onOnboard,
    onOffboard,
    ...rest
  } = props;
  const textColorPrimary = { base: 'secondaryGray.900', _dark: 'white' };
  const textColorSecondary = 'secondaryGray.600';

  const [onboard, setOnboard] = useState<boolean>(() =>
    isOnboard === undefined ? false : isOnboard,
  );

  useEffect(() => {
    if (isOnboard === undefined) {
      return;
    }
    setOnboard(isOnboard);
  }, [isOnboard]);

  const onOnboardClick = async (event: MouseEvent<HTMLButtonElement>) => {
    setOnboard(true); // Disable onboard button
    if (onOnboard === undefined) {
      return;
    }

    await onOnboard(event);
  };

  const onOffBoardClick = async (event: MouseEvent<HTMLButtonElement>) => {
    setOnboard(false); // Disable onboard button
    if (onOffboard === undefined) {
      return;
    }

    await onOffboard(event);
  };

  // Chakra Color Mode
  return (
    <Card
      p="30px"
      py="34px"
      minW={{ base: '300px', md: '700px' }}
      flexDirection={{ base: 'column', md: 'row' }}
      alignItems={{ base: 'start', md: 'center' }}
      justifyContent="space-between"
      {...rest}
    >
      <Flex direction="column">
        <Text fontSize="2xl" color={textColorPrimary} fontWeight="bold">
          {title}
        </Text>
        <Text fontSize="l" color={textColorSecondary}>
          {description}
        </Text>
      </Flex>
      <Flex gap="10px" flexDirection={{ base: 'column', md: 'row' }}>
        <Button
          variant="brand"
          mt={{ base: '20px', md: '0' }}
          _hover={{ bg: { base: 'brand.600', _dark: 'brand.300' } }}
          p="15px 40px"
          h="44px"
          fontWeight="500"
          fontSize="18px"
          py={{ base: '10px', md: '20px', lg: '27px' }}
          px={{ base: '16px', md: '27px', lg: '28px' }}
          w="200px"
          onClick={onOnboardClick}
          ms="auto"
          disabled={onboard} // Disable when not allowed
        >
          Onboard {onboardType}
        </Button>
        <Button
          variant="brand"
          _hover={{ bg: { base: 'brand.600', _dark: 'brand.300' } }}
          p="15px 40px"
          h="44px"
          fontWeight="500"
          fontSize="18px"
          py={{ base: '10px', md: '20px', lg: '27px' }}
          px={{ base: '16px', md: '27px', lg: '28px' }}
          w="200px"
          onClick={onOffBoardClick}
          ms="auto"
          disabled={!onboard} // Initially disabled until onboard button is clicked
        >
          Offboard {onboardType}
        </Button>
      </Flex>
    </Card>
  );
}

export default OnboardCard;
