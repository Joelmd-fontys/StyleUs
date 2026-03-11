import { WardrobeCategory, WardrobeSubcategory } from './types';

interface CategoryOption {
  label: string;
  value?: WardrobeCategory;
}

export const FILTER_CATEGORY_OPTIONS: ReadonlyArray<CategoryOption> = [
  { label: 'All', value: undefined },
  { label: 'Tops', value: 'top' },
  { label: 'Bottoms', value: 'bottom' },
  { label: 'Outerwear', value: 'outerwear' },
  { label: 'Shoes', value: 'shoes' },
  { label: 'Accessories', value: 'accessory' },
  { label: 'Uncategorized', value: 'uncategorized' }
];

export const ITEM_DETAIL_CATEGORY_OPTIONS: ReadonlyArray<WardrobeCategory> = [
  'top',
  'bottom',
  'outerwear',
  'shoes',
  'accessory',
  'unknown',
  'uncategorized'
];

export const UPLOAD_REVIEW_CATEGORY_OPTIONS: ReadonlyArray<WardrobeCategory> = [
  'top',
  'bottom',
  'outerwear',
  'shoes',
  'accessory',
  'uncategorized'
];

export const SUBCATEGORY_LABELS: Record<WardrobeCategory, WardrobeSubcategory[]> = {
  top: [
    't-shirt',
    'tank top',
    'long sleeve',
    'shirt',
    'polo',
    'hoodie',
    'sweatshirt',
    'sweater',
    'jacket',
    'coat'
  ],
  bottom: ['jeans', 'chinos', 'trousers', 'shorts', 'skirt'],
  shoes: ['sneakers', 'boots', 'loafers', 'sandals', 'heels'],
  outerwear: ['puffer', 'fleece', 'rain jacket', 'windbreaker'],
  accessory: ['cap', 'beanie', 'belt', 'bag', 'scarf', 'watch', 'sunglasses'],
  unknown: [],
  uncategorized: []
};

export const getSubcategories = (category: WardrobeCategory): WardrobeSubcategory[] => {
  return SUBCATEGORY_LABELS[category] ?? [];
};

export const toDisplayLabel = (value: string): string => value.replace(/\b\w/g, (char) => char.toUpperCase());
