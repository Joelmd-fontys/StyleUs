import { HttpResponse, http } from 'msw';
import {
  addWardrobeItem,
  findWardrobeItem,
  getWardrobeItems,
  resetWardrobeItems,
  saveWardrobeItem
} from './fixtures';
import { WardrobeItem } from '../domain/types';
import { USE_LIVE_API_ITEMS, USE_LIVE_API_UPLOAD } from '../lib/config';

interface PendingUpload {
  fileName: string;
  contentType: string;
  uploaded: boolean;
}

const pendingUploads = new Map<string, PendingUpload>();

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

const itemHandlers = !USE_LIVE_API_ITEMS
  ? [
      http.get('/items', async ({ request }) => {
        if (shouldFail(request)) {
          return HttpResponse.json({ message: 'Failed to load wardrobe' }, { status: 500 });
        }

        const url = new URL(request.url);
        const category = url.searchParams.get('category');
        const query = url.searchParams.get('q')?.toLowerCase();
        const limit = Number.parseInt(url.searchParams.get('limit') ?? '', 10);
        const offset = Number.parseInt(url.searchParams.get('offset') ?? '', 10);

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

        const start = Number.isNaN(offset) ? 0 : offset;
        const end = Number.isNaN(limit) ? undefined : start + limit;

        // simulate network latency
        await new Promise((resolve) => setTimeout(resolve, 200));

        return HttpResponse.json(filtered.slice(start, end));
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
      http.patch('/items/:id', async ({ params, request }) => {
        if (shouldFail(request)) {
          return HttpResponse.json({ message: 'Failed to update item' }, { status: 500 });
        }

        const id = params.id as string;
        const existing = findWardrobeItem(id);
        if (!existing) {
          return notFound(id);
        }

        const body = (await request.json()) as Partial<WardrobeItem>;
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
    ]
  : [];

const uploadHandlers = !USE_LIVE_API_UPLOAD
  ? [
      http.post('/items/presign', async ({ request }) => {
        if (shouldFail(request)) {
          return HttpResponse.json({ message: 'Upload request failed' }, { status: 500 });
        }

        const body = (await request.json()) as Partial<{
          fileName: string;
          contentType: string;
        }>;
        const itemId =
          typeof crypto !== 'undefined' && 'randomUUID' in crypto
            ? crypto.randomUUID()
            : `item-${Date.now()}`;

        pendingUploads.set(itemId, {
          fileName: body?.fileName ?? 'upload',
          contentType: body?.contentType ?? 'image/png',
          uploaded: false
        });

        const uploadUrl = `/_uploads/${itemId}`;

        return HttpResponse.json({ uploadUrl, itemId });
      }),
      http.put('/_uploads/:itemId', async ({ params, request }) => {
        const itemId = params.itemId as string;
        const pending = pendingUploads.get(itemId);
        if (!pending) {
          return HttpResponse.json({ message: 'Unknown upload session' }, { status: 400 });
        }

        await request.arrayBuffer();
        pendingUploads.set(itemId, { ...pending, uploaded: true });

        return HttpResponse.json({ ok: true }, { status: 200 });
      }),
      http.post('/items/:itemId/complete-upload', async ({ params, request }) => {
        if (shouldFail(request)) {
          return HttpResponse.json({ message: 'Failed to complete upload' }, { status: 500 });
        }

        const itemId = params.itemId as string;
        const pending = pendingUploads.get(itemId);
        if (!pending || !pending.uploaded) {
          return HttpResponse.json(
            { message: 'Upload not ready for completion' },
            { status: 400 }
          );
        }

        const body = (await request.json()) as Partial<{ imageUrl: string }>;
        const now = new Date().toISOString();
        const newItem: WardrobeItem = {
          id: itemId,
          imageUrl: body?.imageUrl ?? '/mock-uploads/default-upload.svg',
          mediumUrl: body?.imageUrl ?? '/mock-uploads/default-upload.svg',
          thumbUrl: body?.imageUrl ?? '/mock-uploads/default-upload.svg',
          category: 'unknown',
          color: 'unknown',
          createdAt: now,
          tags: [],
          imageMetadata: {
            width: 1024,
            height: 768,
            bytes: 245000,
            mimeType: 'image/jpeg',
            checksum: 'mock-upload'
          }
        };

        addWardrobeItem(newItem);
        pendingUploads.delete(itemId);

        return HttpResponse.json(newItem, { status: 200 });
      })
    ]
  : [];

export const handlers = [...itemHandlers, ...uploadHandlers];

export const resetMockState = () => {
  resetWardrobeItems();
  pendingUploads.clear();
};
