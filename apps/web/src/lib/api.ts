import {
  CompleteUploadRequest,
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
  limit?: number;
  offset?: number;
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
  if (typeof filters.limit === 'number') {
    params.set('limit', filters.limit.toString());
  }
  if (typeof filters.offset === 'number') {
    params.set('offset', filters.offset.toString());
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

export const createPresign = async (body: {
  contentType: string;
  fileName: string;
}): Promise<PresignItemResponse> => {
  const response = await fetch(resolveApiUrl('/items/presign'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      contentType: body.contentType,
      fileName: body.fileName
    })
  });

  return handleResponse<PresignItemResponse>(response);
};

interface UploadOptions {
  isLocal?: boolean;
  fileName?: string;
}

/**
 * Upload a file to either a presigned S3 URL or the local API sink.
 */
export const uploadFile = async (url: string, file: File, options: UploadOptions = {}): Promise<void> => {
  const { isLocal = false, fileName } = options;
  const targetUrl = isLocal ? resolveApiUrl(url) : url;
  const headers: Record<string, string> = {
    'Content-Type': file.type
  };

  if (isLocal) {
    headers['X-File-Name'] = fileName ?? file.name;
  }

  const response = await fetch(targetUrl, {
    method: 'PUT',
    headers,
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

export const completeUpload = async (
  id: string,
  body: CompleteUploadRequest
): Promise<GetItemResponse> => {
  const response = await fetch(resolveApiUrl(`/items/${id}/complete-upload`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    body: JSON.stringify(body)
  });

  return handleResponse<GetItemResponse>(response);
};
