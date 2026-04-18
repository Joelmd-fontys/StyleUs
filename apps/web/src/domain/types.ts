import type {
  AIJobState,
  ImageMetadata as GeneratedImageMetadata,
  ItemAIAttributes as GeneratedItemAIAttributes,
  ItemDetail as GeneratedItemDetail
} from './generated/item-contracts';

export type WardrobeCategory =
  | 'top'
  | 'bottom'
  | 'outerwear'
  | 'shoes'
  | 'accessory'
  | 'unknown'
  | 'uncategorized';

export type WardrobeSubcategory =
  | 't-shirt'
  | 'tank top'
  | 'long sleeve'
  | 'shirt'
  | 'polo'
  | 'hoodie'
  | 'sweatshirt'
  | 'sweater'
  | 'jacket'
  | 'coat'
  | 'jeans'
  | 'chinos'
  | 'trousers'
  | 'shorts'
  | 'skirt'
  | 'sneakers'
  | 'boots'
  | 'loafers'
  | 'sandals'
  | 'heels'
  | 'puffer'
  | 'fleece'
  | 'rain jacket'
  | 'windbreaker'
  | 'cap'
  | 'beanie'
  | 'belt'
  | 'bag'
  | 'scarf'
  | 'watch'
  | 'sunglasses';

export type ImageMetadata = GeneratedImageMetadata;

export type ItemAIAttributes = Omit<GeneratedItemAIAttributes, 'subcategory'> & {
  subcategory?: WardrobeSubcategory | null;
};

export type ItemAIJob = AIJobState;

export type WardrobeItem = Omit<GeneratedItemDetail, 'category' | 'subcategory' | 'ai'> & {
  category: WardrobeCategory;
  subcategory?: WardrobeSubcategory | null;
  ai?: ItemAIAttributes | null;
};
