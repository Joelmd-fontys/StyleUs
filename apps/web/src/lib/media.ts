import { resolveApiUrl } from './config';

const FALLBACK_IMAGE = '/mock-uploads/default-upload.svg';

/**
 * Resolve wardrobe media URLs while supporting relative API paths and fallbacks.
 */
export const resolveMediaUrl = (...candidates: Array<string | null | undefined>): string => {
  for (const url of candidates) {
    if (!url) {
      continue;
    }
    if (url.startsWith('http') || url.startsWith('/assets/') || url.startsWith('/mock-uploads/')) {
      return url;
    }
    return resolveApiUrl(url);
  }
  return FALLBACK_IMAGE;
};
