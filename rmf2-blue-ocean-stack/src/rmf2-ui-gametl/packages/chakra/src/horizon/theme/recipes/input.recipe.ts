import { defineRecipe } from '@chakra-ui/react';

export const inputRecipe = defineRecipe({
  variants: {
    variant: {
      search: {
        field: {
          border: 'none',
          py: '11px',
          borderRadius: 'inherit',
          _placeholder: { color: 'secondaryGray.600' },
        },
      },
    },
  },
});
