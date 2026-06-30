import type { InputProps } from '@chakra-ui/react';
import { IconButton, Input, InputGroup } from '@chakra-ui/react';
import { LuSearch } from 'react-icons/lu';

export interface SearchbarProps extends InputProps {
  background?: string | Record<string, string>;
  placeholder?: string;
  borderRadius?: string | number;
}

export function Searchbar(props: SearchbarProps) {
  const { variant, background, placeholder, borderRadius, ...rest } = props;
  // Chakra Color Mode
  const searchIconColor = { base: 'gray.700', _dark: 'white' };
  const inputBg = { base: 'secondaryGray.300', _dark: 'navy.900' };
  const inputText = { bas: 'gray.700', _dark: 'gray.100' };
  return (
    <InputGroup
      w={{ base: '100%', md: '200px' }}
      startElement={
        <IconButton
          aria-label="search"
          display="block"
          bg="inherit"
          borderRadius="inherit"
          _active={{
            bg: 'inherit',
            transform: 'none',
            borderColor: 'transparent',
          }}
          _focus={{
            boxShadow: 'none',
          }}
          color={searchIconColor}
          size="sm"
        >
          <LuSearch />
        </IconButton>
      }
      {...rest}
    >
      <Input
        variant={variant ? variant : 'search'}
        fontSize="sm"
        bg={background ? background : inputBg}
        color={inputText}
        fontWeight="500"
        _placeholder={{ color: 'gray.400', fontSize: '14px' }}
        borderRadius={borderRadius ? borderRadius : '30px'}
        placeholder={placeholder ? placeholder : 'Search...'}
      />
    </InputGroup>
  );
}

export default Searchbar;
