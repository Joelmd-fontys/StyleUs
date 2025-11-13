import { useEffect, useState } from 'react';

const STORAGE_KEY = 'styleus:stats-for-nerds';

const readPreference = () => {
  if (typeof window === 'undefined') {
    return false;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'true';
};

export const useStatsPreference = () => {
  const [enabled, setEnabled] = useState(readPreference);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, enabled ? 'true' : 'false');
  }, [enabled]);

  return [enabled, setEnabled] as const;
};

export const STATS_FOR_NERDS_KEY = STORAGE_KEY;
