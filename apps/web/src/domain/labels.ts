import { SUBCATEGORY_LABELS as BACKEND_SUBCATEGORY_LABELS } from './generated/taxonomy';
import type { WardrobeCategory, WardrobeSubcategory } from './types';

interface CategoryOption {
  label: string;
  value?: WardrobeCategory;
}

const CATEGORY_DISPLAY_LABELS: Record<Exclude<WardrobeCategory, 'unknown' | 'uncategorized'>, string> = {
  top: 'Tops',
  bottom: 'Bottoms',
  outerwear: 'Outerwear',
  shoes: 'Shoes',
  accessory: 'Accessories'
};

const DISPLAY_ORDER: ReadonlyArray<Exclude<WardrobeCategory, 'unknown' | 'uncategorized'>> = [
  'top',
  'bottom',
  'outerwear',
  'shoes',
  'accessory'
];

export const FILTER_CATEGORY_OPTIONS: ReadonlyArray<CategoryOption> = [
  { label: 'All', value: undefined },
  ...DISPLAY_ORDER.map((value) => ({ label: CATEGORY_DISPLAY_LABELS[value], value })),
  { label: 'Uncategorized', value: 'uncategorized' }
];

export const ITEM_DETAIL_CATEGORY_OPTIONS: ReadonlyArray<WardrobeCategory> = [
  ...DISPLAY_ORDER,
  'unknown',
  'uncategorized'
];

export const UPLOAD_REVIEW_CATEGORY_OPTIONS: ReadonlyArray<WardrobeCategory> = [...DISPLAY_ORDER, 'uncategorized'];

export const SUBCATEGORY_LABELS: Record<WardrobeCategory, WardrobeSubcategory[]> = {
  top: [...BACKEND_SUBCATEGORY_LABELS.top],
  bottom: [...BACKEND_SUBCATEGORY_LABELS.bottom],
  shoes: [...BACKEND_SUBCATEGORY_LABELS.shoes],
  outerwear: [...BACKEND_SUBCATEGORY_LABELS.outerwear],
  accessory: [...BACKEND_SUBCATEGORY_LABELS.accessory],
  unknown: [],
  uncategorized: []
};

export const getSubcategories = (category: WardrobeCategory): WardrobeSubcategory[] => {
  return SUBCATEGORY_LABELS[category] ?? [];
};

export const toDisplayLabel = (value: string): string => value.replace(/\b\w/g, (char) => char.toUpperCase());
