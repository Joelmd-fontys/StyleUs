import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';

const STORAGE_KEY = 'styleus:stats-for-nerds';

const readPreference = (): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.localStorage.getItem(STORAGE_KEY) === 'true';
};

export const useStatsPreference = (): readonly [boolean, Dispatch<SetStateAction<boolean>>] => {
  const [enabled, setEnabled] = useState<boolean>(readPreference);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, enabled ? 'true' : 'false');
  }, [enabled]);

  return [enabled, setEnabled] as const;
};
