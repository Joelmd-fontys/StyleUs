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
    return url.startsWith('http') ? url : resolveApiUrl(url);
  }
  return FALLBACK_IMAGE;
};
