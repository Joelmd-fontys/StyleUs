import { ImageMetadata, WardrobeItem } from '../domain/types';

const mockMetadata = (override?: Partial<ImageMetadata>): ImageMetadata => ({
  width: 1024,
  height: 1536,
  bytes: 350000,
  mimeType: 'image/jpeg',
  checksum: 'mock-checksum',
  ...override
});

const seedItems: WardrobeItem[] = [
  {
    id: 'wd-001',
    imageUrl: '/assets/wardrobe/linen-top.svg',
    mediumUrl: '/assets/wardrobe/linen-top.svg',
    thumbUrl: '/assets/wardrobe/linen-top.svg',
    category: 'top',
    color: 'Oatmeal',
    brand: 'North Loom',
    createdAt: '2024-03-02T10:15:00.000Z',
    tags: ['linen', 'casual', 'breathable'],
    imageMetadata: mockMetadata()
  },
  {
    id: 'wd-002',
    imageUrl: '/assets/wardrobe/tailored-trouser.svg',
    mediumUrl: '/assets/wardrobe/tailored-trouser.svg',
    thumbUrl: '/assets/wardrobe/tailored-trouser.svg',
    category: 'bottom',
    color: 'Charcoal',
    brand: 'Line & Form',
    createdAt: '2024-02-21T08:00:00.000Z',
    tags: ['tailored', 'work', 'staple'],
    imageMetadata: mockMetadata()
  },
  {
    id: 'wd-003',
    imageUrl: '/assets/wardrobe/camel-coat.svg',
    mediumUrl: '/assets/wardrobe/camel-coat.svg',
    thumbUrl: '/assets/wardrobe/camel-coat.svg',
    category: 'outerwear',
    color: 'Camel',
    brand: 'Maison Forte',
    createdAt: '2024-01-17T14:40:00.000Z',
    tags: ['outerwear', 'winter'],
    imageMetadata: mockMetadata()
  },
  {
    id: 'wd-004',
    imageUrl: '/assets/wardrobe/sneaker.svg',
    mediumUrl: '/assets/wardrobe/sneaker.svg',
    thumbUrl: '/assets/wardrobe/sneaker.svg',
    category: 'shoes',
    color: 'Glacier White',
    brand: 'Stride Studio',
    createdAt: '2024-03-10T09:12:00.000Z',
    tags: ['sneaker', 'minimal'],
    imageMetadata: mockMetadata()
  },
  {
    id: 'wd-005',
    imageUrl: '/assets/wardrobe/silk-scarf.svg',
    mediumUrl: '/assets/wardrobe/silk-scarf.svg',
    thumbUrl: '/assets/wardrobe/silk-scarf.svg',
    category: 'accessory',
    color: 'Sunset',
    brand: 'Atelier C',
    createdAt: '2024-02-05T18:20:00.000Z',
    tags: ['silk', 'accent'],
    imageMetadata: mockMetadata()
  },
  {
    id: 'wd-006',
    imageUrl: '/assets/wardrobe/vintage-jacket.svg',
    mediumUrl: '/assets/wardrobe/vintage-jacket.svg',
    thumbUrl: '/assets/wardrobe/vintage-jacket.svg',
    category: 'outerwear',
    color: 'Indigo',
    brand: 'Archive 72',
    createdAt: '2023-12-28T12:10:00.000Z',
    tags: ['vintage', 'statement'],
    imageMetadata: mockMetadata()
  }
];

let wardrobeItems = [...seedItems];

export const getWardrobeItems = () => [...wardrobeItems];

export const findWardrobeItem = (id: string) => wardrobeItems.find((item) => item.id === id);

export const addWardrobeItem = (item: WardrobeItem) => {
  wardrobeItems = [item, ...wardrobeItems];
  return item;
};

export const saveWardrobeItem = (item: WardrobeItem) => {
  wardrobeItems = wardrobeItems.map((existing) => (existing.id === item.id ? item : existing));
  return item;
};

export const resetWardrobeItems = () => {
  wardrobeItems = [...seedItems];
};
