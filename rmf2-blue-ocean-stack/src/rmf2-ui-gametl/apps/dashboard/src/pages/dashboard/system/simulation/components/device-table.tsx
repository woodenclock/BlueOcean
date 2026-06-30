import { useState, useEffect } from 'react';
import { Box, Flex, Icon, Table, Text } from '@chakra-ui/react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { MdArrowUpward, MdArrowDownward } from 'react-icons/md';
import { Horizon } from '@rmf2-ui/chakra';
import Card = Horizon.Card;
import type { StateMessage } from './state-message';
import { BrokerNGSILDConfig } from '@/clients';

type RowObj = {
  robotName: string;
  status: string;
  poseX: number;
  poseY: number;
};

const columnHelper = createColumnHelper<RowObj>();

export function DeviceTable() {
  const [_data, setData] = useState<RowObj[]>([]);
  const [filteredData, setFilteredData] = useState<RowObj[]>([]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [_isFetching, setIsFetching] = useState(true);
  const textColor = { base: 'secondaryGray.900', _dark: 'white' };
  const borderColor = { base: 'gray.200', _dark: 'whiteAlpha.100' };

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch data from the first endpoint
        const response1 = await fetch(
          BrokerNGSILDConfig.BASE + '/v1/entities?type=StateMessage',
          {
            method: 'GET',
            headers: {
              Accept: '*/*',
            },
          },
        );

        if (!response1.ok) {
          throw new Error(`HTTP error! status: ${response1.status}`);
        }

        const result1 = await response1.json();
        const transformedData1: RowObj[] = result1.map(
          (item: StateMessage) => ({
            robotName: item.id.replace(/^urn:ngsi-ld:StateMessage:/, ''),
            status: item.status?.value || '',
            poseX: item.pose?.value?.point2D?.x || 0,
            poseY: item.pose?.value?.point2D?.y || 0,
          }),
        );

        const response2 = await fetch(
          BrokerNGSILDConfig.BASE + '/v1/entities?type=StateMessage2',
          {
            method: 'GET',
            headers: {
              Accept: '*/*',
            },
          },
        );

        if (!response2.ok) {
          throw new Error(`HTTP error! status: ${response2.status}`);
        }

        const result2 = await response2.json();
        const transformedData2: RowObj[] = result2.map(
          (item: StateMessage) => ({
            robotName: item.id.replace(/^urn:ngsi-ld:StateMessage:/, ''),
            status: item.status?.value || '',
            poseX: item.pose?.value?.point2D?.x || 0,
            poseY: item.pose?.value?.point2D?.y || 0,
          }),
        );

        // Combine both datasets
        const combinedData = [...transformedData1, ...transformedData2];

        // Remove duplicates based on robotName (keeping the last occurrence)
        const uniqueData = Array.from(
          new Map(combinedData.map((item) => [item.robotName, item])).values(),
        );

        // Set both the raw and filtered data state
        setData(uniqueData);
        setFilteredData(uniqueData);
        setIsFetching(false); // Stop the loading state after data is fetched
      } catch (error) {
        console.error('Failed to fetch data:', error);
        setData([]);
        setFilteredData([]);
        setIsFetching(false);
      }
    };

    fetchData();

    // Fetch data every 5 seconds
    const intervalId = setInterval(fetchData, 5000);
    return () => clearInterval(intervalId);
  }, []);

  const columns = [
    columnHelper.accessor('robotName', {
      id: 'robotName',
      header: () => (
        <Text
          justifyContent="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          Device Name
        </Text>
      ),
      cell: (info) => (
        <Text color={textColor} fontSize="sm" fontWeight="700">
          {info.getValue()}
        </Text>
      ),
    }),

    columnHelper.accessor('status', {
      id: 'status',
      header: () => (
        <Text
          justifyContent="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          Task Status
        </Text>
      ),
      cell: (info) => (
        <Text color={textColor} fontSize="sm" fontWeight="700">
          {info.getValue()}
        </Text>
      ),
    }),

    columnHelper.accessor('poseX', {
      id: 'poseX',
      header: () => (
        <Text
          justifyContent="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          Robot Pose (X)
        </Text>
      ),
      cell: (info) => (
        <Text color={textColor} fontSize="sm" fontWeight="700">
          {info.getValue()}
        </Text>
      ),
    }),

    columnHelper.accessor('poseY', {
      id: 'poseY',
      header: () => (
        <Text
          justifyContent="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          Robot Pose (Y)
        </Text>
      ),
      cell: (info) => {
        return (
          <Text color={textColor} fontSize="sm" fontWeight="700">
            {info.getValue()} {/* Display the formatted time */}
          </Text>
        );
      },
    }),
  ];

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <Card
      flexDirection="column"
      w="100%"
      px="0px"
      overflowX={{ sm: 'scroll', lg: 'hidden' }}
      maxH="500px"
      overflowY="hidden"
    >
      <Flex px="25px" mb="8px" justifyContent="space-between" align="center">
        <Text
          color={textColor}
          fontSize="22px"
          fontWeight="700"
          lineHeight="100%"
        >
          Device Tracker
        </Text>
      </Flex>
      <Box px="20px" mb="24px" mt="12px">
        <Table.ScrollArea height="400px">
          <Table.Root variant="line">
            <Table.Header>
              {table.getHeaderGroups().map((headerGroup) => (
                <Table.Row key={headerGroup.id} bg="transparent">
                  {headerGroup.headers.map((header) => (
                    <Table.ColumnHeader
                      key={header.id}
                      colSpan={header.colSpan}
                      pe="10px"
                      borderColor={borderColor}
                      cursor="pointer"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <Flex
                        justifyContent="space-between"
                        align="center"
                        fontSize={{ sm: '10px', lg: '12px' }}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {{
                          asc: <Icon as={MdArrowUpward} w={4} h={4} />,
                          desc: <Icon as={MdArrowDownward} w={4} h={4} />,
                        }[header.column.getIsSorted() as string] ?? null}
                      </Flex>
                    </Table.ColumnHeader>
                  ))}
                </Table.Row>
              ))}
            </Table.Header>
            <Table.Body>
              {table.getRowModel().rows.map((row) => (
                <Table.Row key={row.id} bg="transparent">
                  {row.getVisibleCells().map((cell) => (
                    <Table.Cell
                      key={cell.id}
                      fontSize={{ sm: '14px' }}
                      minW={{ sm: '150px', md: '200px', lg: 'auto' }}
                      borderColor="transparent"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </Table.Cell>
                  ))}
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>
      </Box>
    </Card>
  );
}
