const base = (import.meta.env.VITE_API_BASE_URL ?? '').toString().trim();

const normalize = (url: string) => url.replace(/\/+$/, '');

export const config = {
  apiBaseUrl: base ? normalize(base) : ''
};

export const resolveApiUrl = (path: string) => {
  if (!config.apiBaseUrl) {
    return path;
  }

  const cleanedPath = path.startsWith('/') ? path.slice(1) : path;
  return `${config.apiBaseUrl}/${cleanedPath}`;
};
