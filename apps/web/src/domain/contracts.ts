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

export interface ReviewFeedback {
  predictedCategory: string | null;
  predictionConfidence: number | null;
  acceptedDirectly: boolean;
}

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
  reviewFeedback?: ReviewFeedback;
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
  attributes?: string[];
  tags: string[];
  tagConfidences?: Record<string, number>;
  confidence?: number | null;
  uncertain?: boolean;
  uncertainFields?: string[];
  pending?: boolean;
  job?: AIJobState | null;
}
