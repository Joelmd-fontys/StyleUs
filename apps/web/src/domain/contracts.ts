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
  subcategory?: WardrobeItem['subcategory'];
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
  subcategory?: string | null;
  subcategoryConfidence?: number | null;
  primaryColor?: string | null;
  primaryColorConfidence?: number | null;
  secondaryColor?: string | null;
  secondaryColorConfidence?: number | null;
  materials?: string[];
  styleTags?: string[];
  tags: string[];
  confidence?: number | null;
}
