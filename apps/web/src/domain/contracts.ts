import { WardrobeItem } from './types';

export type GetItemsResponse = WardrobeItem[];

export interface PresignItemResponse {
  uploadUrl: string;
  itemId: string;
  objectKey?: string;
}

export type GetItemResponse = WardrobeItem;

export type PatchItemResponse = WardrobeItem;

export interface PatchItemRequest {
  category: WardrobeItem['category'];
  color: WardrobeItem['color'];
  brand?: WardrobeItem['brand'];
  tags?: WardrobeItem['tags'];
  subcategory?: string | null;
  primaryColor?: string | null;
  secondaryColor?: string | null;
}

export interface CompleteUploadRequest {
  imageUrl?: string;
  objectKey?: string;
  fileName?: string;
}
