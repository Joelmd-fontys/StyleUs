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

export interface ItemAIAttributes {
  category?: string | null;
  subcategory?: WardrobeSubcategory | null;
  materials: string[];
  styleTags: string[];
  attributes: string[];
  confidence?: number | null;
}

export interface ItemAIJob {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | string;
  attempts: number;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  errorMessage?: string | null;
  pending?: boolean;
}

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
  subcategory?: WardrobeSubcategory | null;
  color: string;
  primaryColor?: string | null;
  secondaryColor?: string | null;
  brand?: string | null;
  createdAt: string;
  tags: string[];
  imageMetadata?: ImageMetadata | null;
  aiConfidence?: number | null;
  ai?: ItemAIAttributes | null;
  aiJob?: ItemAIJob | null;
}
