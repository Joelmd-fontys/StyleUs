import { HttpResponse, http } from 'msw';
import {
  addWardrobeItem,
  findWardrobeItem,
  getWardrobeItems,
  resetWardrobeItems,
  saveWardrobeItem
} from './fixtures';
import { WardrobeItem } from '../domain/types';

const pendingUploads = new Map<
  string,
  {
    filename: string;
    size: number;
    type: string;
  }
>();

const shouldFail = (request: Request) => {
  const url = new URL(request.url);
  return url.searchParams.get('fail') === '1';
};

const notFound = (id: string) =>
  HttpResponse.json(
    { message: `Item with id ${id} not found` },
    {
      status: 404
    }
  );

export const handlers = [
  http.get('/items', async ({ request }) => {
    if (shouldFail(request)) {
      return HttpResponse.json({ message: 'Failed to load wardrobe' }, { status: 500 });
    }

    const url = new URL(request.url);
    const category = url.searchParams.get('category');
    const query = url.searchParams.get('q')?.toLowerCase();

    const items = getWardrobeItems();
    let filtered = [...items];

    if (category && category !== 'all') {
      filtered = filtered.filter((item) => item.category === category);
    }

    if (query) {
      filtered = filtered.filter((item) => {
        const brand = item.brand?.toLowerCase() ?? '';
        const tags = (item.tags ?? []).map((tag) => tag.toLowerCase());
        return brand.includes(query) || tags.some((tag) => tag.includes(query));
      });
    }

    // simulate network latency
    await new Promise((resolve) => setTimeout(resolve, 200));

    return HttpResponse.json(filtered);
  }),

  http.get('/items/:id', ({ params, request }) => {
    if (shouldFail(request)) {
      return HttpResponse.json({ message: 'Failed to fetch item' }, { status: 500 });
    }

    const id = params.id as string;
    const found = findWardrobeItem(id);
    if (!found) {
      return notFound(id);
    }
    return HttpResponse.json(found);
  }),

  http.post('/items', async ({ request }) => {
    if (shouldFail(request)) {
      return HttpResponse.json({ message: 'Upload request failed' }, { status: 500 });
    }

    const body = await request.json();
    const itemId = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `item-${Date.now()}`;

    pendingUploads.set(itemId, {
      filename: body?.filename ?? 'upload',
      size: body?.size ?? 0,
      type: body?.type ?? 'image/png'
    });

    const uploadUrl = `/_uploads/${itemId}`;

    return HttpResponse.json({ uploadUrl, itemId });
  }),

  http.put('/_uploads/:itemId', async ({ params, request }) => {
    const itemId = params.itemId as string;
    if (!pendingUploads.has(itemId)) {
      return HttpResponse.json({ message: 'Unknown upload session' }, { status: 400 });
    }

    // consume the body to mimic real upload
    await request.arrayBuffer();

    const now = new Date().toISOString();
    const newItem: WardrobeItem = {
      id: itemId,
      imageUrl: '/mock-uploads/default-upload.svg',
      category: 'unknown',
      color: 'unknown',
      createdAt: now,
      tags: []
    };

    addWardrobeItem(newItem);
    pendingUploads.delete(itemId);

    return HttpResponse.json({ ok: true }, { status: 200 });
  }),

  http.patch('/items/:id', async ({ params, request }) => {
    if (shouldFail(request)) {
      return HttpResponse.json({ message: 'Failed to update item' }, { status: 500 });
    }

    const id = params.id as string;
    const existing = findWardrobeItem(id);
    if (!existing) {
      return notFound(id);
    }

    const body = await request.json();
    const updated: WardrobeItem = {
      ...existing,
      ...body,
      tags: body.tags ?? existing.tags ?? [],
      brand: body.brand ?? existing.brand,
      color: body.color ?? existing.color,
      category: body.category ?? existing.category
    };

    saveWardrobeItem(updated);

    return HttpResponse.json(updated);
  })
];

export const resetMockState = () => {
  resetWardrobeItems();
  pendingUploads.clear();
};
