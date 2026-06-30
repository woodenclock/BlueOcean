import { ReactNode } from 'react';
import { Flex, Stat, Text } from '@chakra-ui/react';
import { Horizon } from '@rmf2-ui/chakra';
import Card = Horizon.Card;
import CardProps = Horizon.CardProps;

export interface MiniStatisticsCardProps extends CardProps {
  startContent?: ReactNode;
  endContent?: ReactNode;
  name: string;
  growth?: string | number;
  value: string | number;
}

export function MiniStatisticsCard(props: MiniStatisticsCardProps) {
  const { startContent, endContent, name, growth, value, ...rest } = props;
  const textColor = { base: 'secondaryGray.900', _dark: 'white' };
  const textColorSecondary = 'secondaryGray.600';

  return (
    <Card py="15px" {...rest}>
      <Flex
        my="auto"
        h="100%"
        align={{ base: 'center', xl: 'start' }}
        justify={{ base: 'center', xl: 'center' }}
      >
        {startContent}

        <Stat.Root my="auto" ms={startContent ? '18px' : '0px'}>
          <Stat.Label
            lineHeight="100%"
            color={textColorSecondary}
            fontSize={{
              base: 'sm',
            }}
          >
            {name}
          </Stat.Label>
          <Stat.ValueText
            color={textColor}
            fontSize={{
              base: '2xl',
            }}
          >
            {value}
          </Stat.ValueText>
          {growth ? (
            <Flex align="center">
              <Text color="green.500" fontSize="xs" fontWeight="700" me="5px">
                {growth}
              </Text>
              <Text color="secondaryGray.600" fontSize="xs" fontWeight="400">
                since last month
              </Text>
            </Flex>
          ) : null}
        </Stat.Root>
        <Flex ms="auto" w="max-content">
          {endContent}
        </Flex>
      </Flex>
    </Card>
  );
}
