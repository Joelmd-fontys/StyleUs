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
  primaryColor?: string | null;
  secondaryColor?: string | null;
}

export interface CompleteUploadRequest {
  imageUrl?: string;
  objectKey?: string;
  fileName?: string;
}

export interface AIPreviewResponse {
  category?: string | null;
  categoryConfidence?: number | null;
  primaryColor?: string | null;
  primaryColorConfidence?: number | null;
  secondaryColor?: string | null;
  secondaryColorConfidence?: number | null;
  tags: string[];
  confidence?: number | null;
}
