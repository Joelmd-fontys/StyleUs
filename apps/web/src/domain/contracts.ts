import { WardrobeItem } from './types';

export type GetItemsResponse = WardrobeItem[];

export interface PresignItemResponse {
  uploadUrl: string;
  itemId: string;
}

export type GetItemResponse = WardrobeItem;

export type PatchItemResponse = WardrobeItem;

export interface PatchItemRequest {
  category: WardrobeItem['category'];
  color: WardrobeItem['color'];
  brand?: WardrobeItem['brand'];
  tags?: WardrobeItem['tags'];
}
