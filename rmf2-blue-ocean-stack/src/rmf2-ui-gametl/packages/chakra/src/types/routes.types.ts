import type { JSX } from 'react';

export interface RoutesType {
  name: string;
  icon?: JSX.Element;
  /** In-app route. Omit for section parents (sidebar accordion only). */
  path?: string;
  /** External URL — opens in a new tab when set instead of `path`. */
  href?: string;
  children?: RoutesType[];
}
