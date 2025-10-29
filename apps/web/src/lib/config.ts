const rawBase = (import.meta.env.VITE_API_BASE_URL ?? '').toString().trim() || 'http://127.0.0.1:8000';
export const API_BASE = rawBase;

const normalize = (url: string) => url.replace(/\/+$/, '');

const normalizedBase = rawBase ? normalize(rawBase) : '';

const readFlag = (value: unknown, fallback: boolean) => {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (['true', '1', 'yes', 'y'].includes(normalized)) {
      return true;
    }
    if (['false', '0', 'no', 'n'].includes(normalized)) {
      return false;
    }
  }
  if (typeof value === 'boolean') {
    return value;
  }
  return fallback;
};

export const USE_LIVE_API_ITEMS = readFlag(import.meta.env.VITE_USE_LIVE_API_ITEMS, true);
export const USE_LIVE_API_UPLOAD = readFlag(import.meta.env.VITE_USE_LIVE_API_UPLOAD, true);

export const config = {
  apiBaseUrl: normalizedBase
};

export const resolveApiUrl = (path: string) => {
  if (!config.apiBaseUrl) {
    return path;
  }

  const cleanedPath = path.startsWith('/') ? path.slice(1) : path;
  return `${config.apiBaseUrl}/${cleanedPath}`;
};
