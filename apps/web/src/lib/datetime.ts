const formatWithOptions = (value: string, options: Intl.DateTimeFormatOptions): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return new Intl.DateTimeFormat(undefined, { ...options, timeZone: 'UTC' }).format(date);
};

export const formatUtcDate = (value: string): string =>
  formatWithOptions(value, { month: 'short', day: 'numeric', year: 'numeric' });

export const formatUtcTime = (value: string): string =>
  formatWithOptions(value, { hour: 'numeric', minute: 'numeric' });
