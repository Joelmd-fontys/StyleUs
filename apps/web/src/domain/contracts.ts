import type {
  CompleteUploadRequest,
  ItemAIPreview,
  ItemReviewFeedback,
  ItemUpdate,
  PresignResponse
} from './generated/item-contracts';
import type { WardrobeItem } from './types';

export type GetItemsResponse = WardrobeItem[];

export type PresignItemResponse = PresignResponse;

export type GetItemResponse = WardrobeItem;

export type PatchItemResponse = WardrobeItem;

export type ReviewFeedback = ItemReviewFeedback;

export type PatchItemRequest = Omit<ItemUpdate, 'category' | 'subcategory' | 'color' | 'brand' | 'tags'> & {
  category: WardrobeItem['category'];
  subcategory?: WardrobeItem['subcategory'];
  color: WardrobeItem['color'];
  brand?: WardrobeItem['brand'];
  tags?: WardrobeItem['tags'];
};

export type { CompleteUploadRequest };

export type AIPreviewResponse = ItemAIPreview;
