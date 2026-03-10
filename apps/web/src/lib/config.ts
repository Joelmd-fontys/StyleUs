export type AppEnv = 'local' | 'staging' | 'production';

const normalize = (url: string): string => url.replace(/\/+$/, '');

const readAppEnv = (value: unknown): AppEnv => {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized === 'staging' || normalized === 'production') {
      return normalized;
    }
  }
  return 'local';
};

const readString = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

export const APP_ENV: AppEnv = readAppEnv(import.meta.env.VITE_APP_ENV);
const defaultApiBase = APP_ENV === 'local' ? 'http://127.0.0.1:8000' : '';
const rawBase = readString(import.meta.env.VITE_API_BASE_URL) || defaultApiBase;
export const API_BASE: string = rawBase;

const normalizedBase: string = rawBase ? normalize(rawBase) : '';
export const SUPABASE_URL: string = readString(import.meta.env.VITE_SUPABASE_URL);
export const SUPABASE_ANON_KEY: string = readString(import.meta.env.VITE_SUPABASE_ANON_KEY);

const readFlag = (value: unknown, fallback: boolean): boolean => {
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

export const config: Readonly<{
  appEnv: AppEnv;
  apiBaseUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
}> = {
  appEnv: APP_ENV,
  apiBaseUrl: normalizedBase,
  supabaseUrl: SUPABASE_URL,
  supabaseAnonKey: SUPABASE_ANON_KEY
};

export const resolveApiUrl = (path: string): string => {
  if (!config.apiBaseUrl) {
    return path;
  }

  const cleanedPath = path.startsWith('/') ? path.slice(1) : path;
  return `${config.apiBaseUrl}/${cleanedPath}`;
};
