import { defineRecipe } from '@chakra-ui/react';

export const buttonRecipe = defineRecipe({
  base: {
    borderRadius: '16px',
    boxShadow: '45px 76px 113px 7px rgba(112, 144, 176, 0.08)',
    transition: '.25s all ease',
    boxSizing: 'border-box',
    _focus: {
      boxShadow: 'none',
    },
    _active: {
      boxShadow: 'none',
    },
  },
  variants: {
    variant: {
      outline: {
        borderRadius: '16px',
      },
      brand: {
        bg: { base: 'brand.500', _dark: 'brand.400' },
        color: 'white',
        _focus: {
          bg: { base: 'brand.500', _dark: 'brand.400' },
        },
        _active: {
          bg: { base: 'brand.500', _dark: 'brand.400' },
        },
        _hover: {
          bg: { base: 'brand.600', _dark: 'brand.400' },
        },
      },
      darkBrand: {
        bg: { base: 'brand.900', _dark: 'brand.400' },
        color: 'white',
        _focus: {
          bg: { base: 'brand.900', _dark: 'brand.400' },
        },
        _active: {
          bg: { base: 'brand.900', _dark: 'brand.400' },
        },
        _hover: {
          bg: { base: 'brand.800', _dark: 'brand.400' },
        },
      },
      lightBrand: {
        bg: { base: '#F2EFFF', _dark: 'whiteAlpha.100' },
        color: { base: 'brand.500', _dark: 'white' },
        _focus: {
          bg: { base: '#F2EFFF', _dark: 'whiteAlpha.100' },
        },
        _active: {
          bg: { base: 'secondaryGray.300', _dark: 'whiteAlpha.100' },
        },
        _hover: {
          bg: { base: 'secondaryGray.400', _dark: 'whiteAlpha.200' },
        },
      },
      light: {
        bg: { base: 'secondaryGray.300', _dark: 'whiteAlpha.100' },
        color: { base: 'secondaryGray.900', _dark: 'white' },
        _focus: {
          bg: { base: 'secondaryGray.300', _dark: 'whiteAlpha.100' },
        },
        _active: {
          bg: { base: 'secondaryGray.300', _dark: 'whiteAlpha.100' },
        },
        _hover: {
          bg: { base: 'secondaryGray.400', _dark: 'whiteAlpha.200' },
        },
      },
      action: {
        fontWeight: '500',
        borderRadius: '50px',
        bg: { base: 'secondaryGray.300', _dark: 'brand.400' },
        color: { base: 'brand.500', _dark: 'white' },
        _focus: {
          bg: { base: 'secondaryGray.300', _dark: 'brand.400' },
        },
        _active: { bg: { base: 'secondaryGray.300', _dark: 'brand.400' } },
        _hover: {
          bg: { base: 'secondaryGray.200', _dark: 'brand.400' },
        },
      },
      setup: {
        fontWeight: '500',
        borderRadius: '50px',
        bg: { base: 'transparent', _dark: 'brand.400' },
        border: { base: '1px solid', _dark: '0px solid' },
        borderColor: { base: 'secondaryGray.400', _dark: 'transparent' },
        color: { base: 'secondaryGray.900', _dark: 'white' },
        _focus: {
          bg: { base: 'transparent', _dark: 'brand.400' },
        },
        _active: { bg: { base: 'transparent', _dark: 'brand.400' } },
        _hover: {
          bg: { base: 'secondaryGray.100', _dark: 'brand.400' },
        },
      },
    },
  },
});
