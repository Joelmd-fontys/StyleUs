import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { getAccessTokenMock, getSupabaseClientMock, uploadToSignedUrlMock, fromMock } = vi.hoisted(() => {
  const uploadToSignedUrl = vi.fn();
  const from = vi.fn(() => ({
    uploadToSignedUrl
  }));

  return {
    getAccessTokenMock: vi.fn(),
    getSupabaseClientMock: vi.fn(),
    uploadToSignedUrlMock: uploadToSignedUrl,
    fromMock: from
  };
});

vi.mock('./supabase', () => ({
  getAccessToken: getAccessTokenMock,
  getSupabaseClient: getSupabaseClientMock
}));

import { completeUpload, createPresign, getItemAIPreview, getItems, patchItem, uploadFile } from './api';

describe('api bearer propagation', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    getAccessTokenMock.mockReset();
    getSupabaseClientMock.mockReset();
    uploadToSignedUrlMock.mockReset();
    fromMock.mockReset();
    fromMock.mockImplementation(() => ({
      uploadToSignedUrl: uploadToSignedUrlMock
    }));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('attaches the Supabase access token to API reads', async () => {
    getAccessTokenMock.mockResolvedValue('token-123');
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await getItems();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items',
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: 'Bearer token-123'
        })
      })
    );
  });

  it('posts upload initiation payloads to the presign endpoint', async () => {
    getAccessTokenMock.mockResolvedValue('token-presign');
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ itemId: 'item-1', uploadUrl: '/_uploads/item-1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await createPresign({
      contentType: 'image/png',
      fileName: 'look.png',
      fileSize: 1234
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items/presign',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: 'Bearer token-presign',
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify({
          contentType: 'image/png',
          fileName: 'look.png',
          fileSize: 1234
        })
      })
    );
  });

  it('uploads through the browser Supabase client when a signed upload token is present', async () => {
    const file = new File(['image-bytes'], 'look.png', { type: 'image/png' });

    getSupabaseClientMock.mockReturnValue({
      storage: {
        from: fromMock
      }
    });
    uploadToSignedUrlMock.mockResolvedValue({ error: null });

    await uploadFile('https://storage.example/upload', file, {
      objectKey: 'users/item/source/look.png',
      uploadToken: 'signed-token',
      bucket: 'wardrobe-images'
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(fromMock).toHaveBeenCalledWith('wardrobe-images');
    expect(uploadToSignedUrlMock).toHaveBeenCalledWith('users/item/source/look.png', 'signed-token', file, {
      contentType: 'image/png',
      upsert: false
    });
  });

  it('includes review feedback in patch payloads', async () => {
    getAccessTokenMock.mockResolvedValue('token-456');
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 'item-1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await patchItem('item-1', {
      category: 'top',
      color: 'Black',
      reviewFeedback: {
        predictedCategory: 'top',
        predictionConfidence: 0.84,
        acceptedDirectly: true
      }
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items/item-1',
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: 'Bearer token-456',
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify({
          category: 'top',
          color: 'Black',
          reviewFeedback: {
            predictedCategory: 'top',
            predictionConfidence: 0.84,
            acceptedDirectly: true
          }
        })
      })
    );
  });

  it('posts upload finalization payloads to the complete-upload endpoint', async () => {
    getAccessTokenMock.mockResolvedValue('token-complete');
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 'item-1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );

    await completeUpload('item-1', {
      objectKey: 'users/item/source/look.png',
      fileName: 'look.png'
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items/item-1/complete-upload',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: 'Bearer token-complete',
          'Content-Type': 'application/json'
        }),
        body: JSON.stringify({
          objectKey: 'users/item/source/look.png',
          fileName: 'look.png'
        })
      })
    );
  });

  it('falls back to fetch for mock upload endpoints', async () => {
    const file = new File(['image-bytes'], 'look.png', { type: 'image/png' });

    getAccessTokenMock.mockResolvedValue('token-abc');
    fetchMock.mockResolvedValue(new Response(null, { status: 201 }));

    await uploadFile('/_uploads/item-123', file);

    expect(fetchMock).toHaveBeenCalledWith(
      '/_uploads/item-123',
      expect.objectContaining({
        method: 'PUT',
        headers: { 'Content-Type': 'image/png' },
        body: file
      })
    );
  });

  it('keeps pending AI preview fields nullable while the job is in flight', async () => {
    getAccessTokenMock.mockResolvedValue('token-preview');
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          category: null,
          subcategory: null,
          pending: true,
          job: {
            id: 'job-1',
            status: 'pending',
            attempts: 0,
            createdAt: '2026-04-14T12:00:00Z',
            startedAt: null,
            completedAt: null,
            errorMessage: null,
            pending: true
          }
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        }
      )
    );

    const preview = await getItemAIPreview('item-preview');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items/item-preview/ai-preview',
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: 'application/json',
          Authorization: 'Bearer token-preview'
        })
      })
    );
    expect(preview.category).toBeNull();
    expect(preview.subcategory).toBeNull();
    expect(preview.pending).toBe(true);
    expect(preview.job?.status).toBe('pending');
    expect(preview.job?.attempts).toBe(0);
  });
});
