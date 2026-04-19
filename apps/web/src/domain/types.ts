import type {
  AIJobState,
  ImageMetadata as GeneratedImageMetadata,
  ItemAIAttributes as GeneratedItemAIAttributes,
  ItemDetail as GeneratedItemDetail
} from './generated/item-contracts';
import type { BackendCategory, BackendSubcategory } from './generated/taxonomy';

export type WardrobeCategory = BackendCategory | 'unknown' | 'uncategorized';

export type WardrobeSubcategory = BackendSubcategory;

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
