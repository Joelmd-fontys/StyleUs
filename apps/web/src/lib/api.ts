import type {
  CompleteUploadRequest,
  ItemAIPreview,
  ItemUpdate,
  PresignRequest,
  PresignResponse
} from '../domain/generated/item-contracts';
import type { WardrobeItem } from '../domain/types';
import { resolveApiUrl } from './config';
import { getAccessToken, getSupabaseClient } from './supabase';

export interface ItemFilters {
  category?: string;
  q?: string;
  limit?: number;
  offset?: number;
  createdSince?: string;
}

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
};

const buildHeaders = async (headers: HeadersInit = {}): Promise<HeadersInit> => {
  const token = await getAccessToken();
  if (!token) {
    return headers;
  }

  return {
    ...headers,
    Authorization: `Bearer ${token}`
  };
};

export const getItems = async (filters: ItemFilters = {}): Promise<WardrobeItem[]> => {
  const url = resolveApiUrl('/items');
  const params = new URLSearchParams();
  if (filters.category) {
    params.set('category', filters.category);
  }
  if (filters.q) {
    params.set('q', filters.q);
  }
  if (typeof filters.limit === 'number') {
    params.set('limit', filters.limit.toString());
  }
  if (typeof filters.offset === 'number') {
    params.set('offset', filters.offset.toString());
  }
  if (filters.createdSince) {
    params.set('createdSince', filters.createdSince);
  }
  const requestUrl = params.toString() ? `${url}?${params.toString()}` : url;

  const response = await fetch(requestUrl, {
    headers: await buildHeaders({ Accept: 'application/json' })
  });

  return handleResponse<WardrobeItem[]>(response);
};

export const getItem = async (id: string): Promise<WardrobeItem> => {
  const response = await fetch(resolveApiUrl(`/items/${id}`), {
    headers: await buildHeaders({ Accept: 'application/json' })
  });
  return handleResponse<WardrobeItem>(response);
};

export const createPresign = async (body: PresignRequest): Promise<PresignResponse> => {
  const response = await fetch(resolveApiUrl('/items/presign'), {
    method: 'POST',
    headers: await buildHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
    body: JSON.stringify({
      contentType: body.contentType,
      fileName: body.fileName,
      fileSize: body.fileSize
    })
  });

  return handleResponse<PresignResponse>(response);
};

interface UploadOptions {
  isLocal?: boolean;
  fileName?: string;
  objectKey?: string;
  uploadToken?: string;
  bucket?: string;
}

/**
 * Upload a file through either a Supabase signed upload token or a local mock endpoint.
 */
export const uploadFile = async (url: string, file: File, options: UploadOptions = {}): Promise<void> => {
  const { isLocal = false, fileName, objectKey, uploadToken, bucket } = options;

  if (uploadToken && objectKey && bucket) {
    const client = getSupabaseClient();
    if (!client) {
      throw new Error('Supabase Storage is not configured in the web client.');
    }

    const { error } = await client.storage.from(bucket).uploadToSignedUrl(objectKey, uploadToken, file, {
      contentType: file.type,
      upsert: false
    });

    if (error) {
      throw error;
    }
    return;
  }

  const targetUrl = isLocal ? resolveApiUrl(url) : url;
  const baseHeaders: Record<string, string> = {
    'Content-Type': file.type
  };

  if (isLocal) {
    baseHeaders['X-File-Name'] = fileName ?? file.name;
  }

  const headers = isLocal ? await buildHeaders(baseHeaders) : baseHeaders;

  const response = await fetch(targetUrl, {
    method: 'PUT',
    headers,
    body: file
  });

  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }
};

export const patchItem = async (id: string, body: ItemUpdate): Promise<WardrobeItem> => {
  const response = await fetch(resolveApiUrl(`/items/${id}`), {
    method: 'PATCH',
    headers: await buildHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json'
    }),
    body: JSON.stringify(body)
  });

  return handleResponse<WardrobeItem>(response);
};

export const deleteItem = async (id: string): Promise<void> => {
  const response = await fetch(resolveApiUrl(`/items/${id}`), {
    method: 'DELETE',
    headers: await buildHeaders({ Accept: 'application/json' })
  });

  await handleResponse<void>(response);
};

export const completeUpload = async (id: string, body: CompleteUploadRequest): Promise<WardrobeItem> => {
  const response = await fetch(resolveApiUrl(`/items/${id}/complete-upload`), {
    method: 'POST',
    headers: await buildHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json'
    }),
    body: JSON.stringify(body)
  });

  return handleResponse<WardrobeItem>(response);
};

export const getItemAIPreview = async (id: string): Promise<ItemAIPreview> => {
  const response = await fetch(resolveApiUrl(`/items/${id}/ai-preview`), {
    headers: await buildHeaders({ Accept: 'application/json' })
  });

  return handleResponse<ItemAIPreview>(response);
};
