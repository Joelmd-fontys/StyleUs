import { WardrobeCategory, WardrobeSubcategory } from './types';

export const CATEGORY_LABELS: WardrobeCategory[] = [
  'top',
  'bottom',
  'shoes',
  'outerwear',
  'accessory',
  'unknown',
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

export const STYLE_LABELS = ['streetwear', 'sport', 'minimal', 'retro', 'outdoor', 'formal', 'grunge'];

export const MATERIAL_LABELS = [
  'cotton',
  'denim',
  'wool',
  'leather',
  'nylon',
  'knit',
  'fleece',
  'suede',
  'mesh'
];

export const getSubcategories = (category: WardrobeCategory): WardrobeSubcategory[] => {
  return SUBCATEGORY_LABELS[category] ?? [];
};
