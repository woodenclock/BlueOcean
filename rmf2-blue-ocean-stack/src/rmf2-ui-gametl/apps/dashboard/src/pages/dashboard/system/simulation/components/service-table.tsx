import { useState } from 'react';
import { Box, Flex, Icon, Table, Text } from '@chakra-ui/react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { Horizon } from '@rmf2-ui/chakra';
import Card = Horizon.Card;
import { MdCancel, MdCheckCircle, MdOutlineError } from 'react-icons/md';
import { BsQuestionCircleFill } from 'react-icons/bs';

type RowObj = {
  name: string;
  status: string;
  type: string;
};

const columnHelper = createColumnHelper<RowObj>();

export interface ServiceTableProps {
  serviceInfo: RowObj[];
}

export function ServiceTable(props: ServiceTableProps) {
  const { serviceInfo: tableData } = props;
  const [sorting, setSorting] = useState<SortingState>([]);
  const textColor = { base: 'secondaryGray.900', _dark: 'white' };
  const borderColor = { base: 'gray.200', _dark: 'whiteAlpha.100' };
  const defaultData = tableData;
  const columns = [
    columnHelper.accessor('name', {
      id: 'name',
      header: () => (
        <Text
          justifyContent="space-between"
          alignItems="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          SERVICE NAME
        </Text>
      ),
      cell: (info) => (
        <Flex align="center">
          <Text color={textColor} fontSize="sm" fontWeight="700">
            {info.getValue()}
          </Text>
        </Flex>
      ),
    }),
    columnHelper.accessor('type', {
      id: 'type',
      header: () => (
        <Text
          justifyContent="space-between"
          alignItems="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          SERVICE TYPE
        </Text>
      ),
      cell: (info) => (
        <Flex align="center">
          <Text color={textColor} fontSize="sm" fontWeight="700">
            {info.getValue()}
          </Text>
        </Flex>
      ),
    }),
    columnHelper.accessor('status', {
      id: 'status',
      header: () => (
        <Text
          justifyContent="space-between"
          alignItems="center"
          fontSize={{ sm: '10px', lg: '12px' }}
          color="gray.400"
        >
          STATUS
        </Text>
      ),
      cell: (info) => (
        <Flex align="center">
          <Icon
            w="24px"
            h="24px"
            me="5px"
            color={
              info.getValue() === 'Online'
                ? 'green.500'
                : info.getValue() === 'Offline'
                  ? 'red.500'
                  : info.getValue() === 'Error'
                    ? 'orange.500'
                    : 'gray.500'
            }
            as={
              info.getValue() === 'Online'
                ? MdCheckCircle
                : info.getValue() === 'Offline'
                  ? MdCancel
                  : info.getValue() === 'Error'
                    ? MdOutlineError
                    : BsQuestionCircleFill
            }
          />
          <Text color={textColor} fontSize="sm" fontWeight="700">
            {info.getValue()}
          </Text>
        </Flex>
      ),
    }),
  ];
  const [data, _setData] = useState(() => [...defaultData]);
  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    debugTable: true,
  });
  return (
    <Card
      flexDirection="column"
      w="100%"
      px="0px"
      overflowX={{ sm: 'scroll', lg: 'hidden' }}
    >
      <Flex px="15px" mb="8px" justifyContent="space-between" align="center">
        <Text
          color={textColor}
          fontSize="22px"
          fontWeight="700"
          lineHeight="100%"
        >
          Service Tracker
        </Text>
      </Flex>
      <Box px="20px">
        <Table.ScrollArea maxHeight="400px">
          <Table.Root variant="line" mt="12px">
            <Table.Header>
              {table.getHeaderGroups().map((headerGroup) => (
                <Table.Row key={headerGroup.id} bg="transparent">
                  {headerGroup.headers.map((header) => {
                    return (
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
                          color="gray.400"
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          {{
                            asc: '',
                            desc: '',
                          }[header.column.getIsSorted() as string] ?? null}
                        </Flex>
                      </Table.ColumnHeader>
                    );
                  })}
                </Table.Row>
              ))}
            </Table.Header>
            <Table.Body>
              {table
                .getRowModel()
                .rows.slice(0, 11)
                .map((row) => {
                  return (
                    <Table.Row key={row.id} bg="transparent">
                      {row.getVisibleCells().map((cell) => {
                        return (
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
                        );
                      })}
                    </Table.Row>
                  );
                })}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>
      </Box>
    </Card>
  );
}
