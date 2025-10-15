import {
  GetItemResponse,
  GetItemsResponse,
  PatchItemRequest,
  PatchItemResponse,
  PresignItemResponse
} from '../domain/contracts';
import { resolveApiUrl } from './config';

export interface ItemFilters {
  category?: string;
  q?: string;
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

export const getItems = async (filters: ItemFilters = {}): Promise<GetItemsResponse> => {
  const url = resolveApiUrl('/items');
  const params = new URLSearchParams();
  if (filters.category) {
    params.set('category', filters.category);
  }
  if (filters.q) {
    params.set('q', filters.q);
  }
  const requestUrl = params.toString() ? `${url}?${params.toString()}` : url;

  const response = await fetch(requestUrl, {
    headers: { Accept: 'application/json' }
  });

  return handleResponse<GetItemsResponse>(response);
};

export const getItem = async (id: string): Promise<GetItemResponse> => {
  const response = await fetch(resolveApiUrl(`/items/${id}`), {
    headers: { Accept: 'application/json' }
  });
  return handleResponse<GetItemResponse>(response);
};

export const requestUpload = async (file: File): Promise<PresignItemResponse> => {
  const response = await fetch(resolveApiUrl('/items'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      filename: file.name,
      size: file.size,
      type: file.type
    })
  });

  return handleResponse<PresignItemResponse>(response);
};

export const uploadFile = async (url: string, file: File) => {
  const response = await fetch(url, {
    method: 'PUT',
    body: file
  });

  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }
};

export const patchItem = async (id: string, body: PatchItemRequest): Promise<PatchItemResponse> => {
  const response = await fetch(resolveApiUrl(`/items/${id}`), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify(body)
  });

  return handleResponse<PatchItemResponse>(response);
};
