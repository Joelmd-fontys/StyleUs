export type WardrobeCategory = 'top' | 'bottom' | 'outerwear' | 'shoes' | 'accessory' | 'unknown';

export interface WardrobeItem {
  id: string;
  imageUrl: string;
  category: WardrobeCategory;
  color: string;
  brand?: string;
  createdAt: string;
  tags?: string[];
}
