export type WardrobeCategory =
  | 'top'
  | 'bottom'
  | 'outerwear'
  | 'shoes'
  | 'accessory'
  | 'unknown'
  | 'uncategorized';

export interface ImageMetadata {
  width?: number | null;
  height?: number | null;
  bytes?: number | null;
  mimeType?: string | null;
  checksum?: string | null;
}

export interface WardrobeItem {
  id: string;
  imageUrl?: string | null;
  thumbUrl?: string | null;
  mediumUrl?: string | null;
  category: WardrobeCategory;
  color: string;
  brand?: string;
  createdAt: string;
  tags: string[];
  imageMetadata?: ImageMetadata | null;
}
