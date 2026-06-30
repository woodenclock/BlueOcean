import { useState, useEffect, MouseEventHandler, MouseEvent } from 'react';
import { Button, Flex, Text, Icon } from '@chakra-ui/react';
import type { IconType } from 'react-icons';
import { MdCancel, MdCheckCircle, MdOutlineError } from 'react-icons/md';
import { Horizon } from '@rmf2-ui/chakra';
import Card = Horizon.Card;
import CardProps = Horizon.CardProps;

export type InitializationState = 'disabled' | 'pending' | 'initialized';

export interface InitializeCardProps extends CardProps {
  title: string;
  description: string;
  initializeType: string;
  value?: InitializationState;
  onInitialize?: MouseEventHandler<HTMLButtonElement>;
}

export function InitializeCard(props: InitializeCardProps) {
  const {
    title,
    description,
    initializeType,
    value: valueUnmanaged,
    onInitialize,
    ...rest
  } = props;
  const textColorPrimary = { base: 'secondaryGray.900', _dark: 'white' };
  const textColorSecondary = 'secondaryGray.600';

  const [value, setValue] = useState<InitializationState>(() =>
    valueUnmanaged === undefined ? 'disabled' : valueUnmanaged,
  );

  useEffect(() => {
    if (valueUnmanaged === undefined) {
      return;
    }
    setValue(valueUnmanaged);
  }, [valueUnmanaged]);

  const onInitializeClick = async (e: MouseEvent<HTMLButtonElement>) => {
    setValue('initialized');
    if (onInitialize === undefined) {
      return;
    }

    await onInitialize(e);
  };

  const stateIconColor = (value: InitializationState): string => {
    if (value === 'initialized') {
      return 'green.500';
    }

    if (value === 'pending') {
      return 'yellow.500';
    }
    return 'red.500';
  };

  const stateIcon = (value: InitializationState): IconType => {
    if (value === 'initialized') {
      return MdCheckCircle;
    }

    if (value === 'pending') {
      return MdOutlineError;
    }
    return MdCancel;
  };

  return (
    <Card
      p="30px"
      py="34px"
      flexDirection={{ base: 'column', md: 'row', lg: 'row' }}
      alignItems={{ base: 'start', md: 'center' }}
      {...rest}
    >
      <Flex direction="column">
        <Text fontSize="2xl" color={textColorPrimary} fontWeight="bold">
          Initialize System
        </Text>

        <Flex direction="row">
          <Text fontSize="l" color={textColorSecondary}>
            {description}
          </Text>

          <Icon
            w="24px"
            h="24px"
            ml="10px"
            color={stateIconColor(value)}
            as={stateIcon(value)}
          />
        </Flex>
      </Flex>
      <Button
        colorScheme="green"
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
        me="20px"
        onClick={onInitializeClick}
        disabled={value !== 'pending'}
        ms={{ base: '0px', md: 'auto' }}
      >
        Initialize {initializeType}
      </Button>
    </Card>
  );
}
