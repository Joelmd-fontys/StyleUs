import { WardrobeItem } from './types';

export type GetItemsResponse = WardrobeItem[];

export interface PresignItemResponse {
  uploadUrl: string;
  itemId: string;
  objectKey?: string;
  uploadToken?: string;
  bucket?: string;
}

export type GetItemResponse = WardrobeItem;

export type PatchItemResponse = WardrobeItem;

export interface AIJobState {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | string;
  attempts: number;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  errorMessage?: string | null;
  pending?: boolean;
}

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
  pending?: boolean;
  job?: AIJobState | null;
}
