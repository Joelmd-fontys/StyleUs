import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WardrobeItem } from '../domain/types';
import Dashboard from './Dashboard';
import { useWardrobeStore } from '../store/wardrobe';

const { getItemsMock } = vi.hoisted(() => ({
  getItemsMock: vi.fn()
}));

vi.mock('../lib/api', () => ({
  getItems: getItemsMock
}));

vi.mock('../hooks/useStatsPreference', () => ({
  useStatsPreference: () => [false]
}));

const baseState = useWardrobeStore.getState();

const makeItem = (index: number): WardrobeItem => ({
  id: `item-${index}`,
  imageUrl: `/image-${index}.jpg`,
  mediumUrl: `/medium-${index}.jpg`,
  thumbUrl: `/thumb-${index}.jpg`,
  category: index % 2 === 0 ? 'top' : 'shoes',
  subcategory: index % 2 === 0 ? 't-shirt' : 'sneakers',
  color: 'black',
  brand: `Brand ${index}`,
  createdAt: new Date(Date.UTC(2026, 3, index + 1, 12, 0, 0)).toISOString(),
  tags: index === 0 ? ['favorite'] : []
});

describe('Dashboard', () => {
  beforeEach(() => {
    getItemsMock.mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    useWardrobeStore.setState(baseState, true);
    vi.useRealTimers();
  });

  it('loads recent items with a four-item cap for the dashboard rail', async () => {
    useWardrobeStore.setState((state) => ({
      ...state,
      items: [makeItem(0), makeItem(1), makeItem(2)],
      loading: false,
      loadItems: vi.fn().mockResolvedValue(undefined)
    }));

    getItemsMock.mockResolvedValue([makeItem(4), makeItem(3), makeItem(2), makeItem(1), makeItem(0)]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(getItemsMock).toHaveBeenCalledWith({ limit: 4, createdSince: undefined }));
    expect(await screen.findByText('Brand 4')).toBeInTheDocument();
    expect(screen.getByText('Brand 3')).toBeInTheDocument();
    expect(screen.getByText('Brand 2')).toBeInTheDocument();
    expect(screen.getByText('Brand 1')).toBeInTheDocument();
    expect(screen.queryByText('Brand 0')).not.toBeInTheDocument();
  });

  it('clears the recent list until refresh and refetches with createdSince', async () => {
    useWardrobeStore.setState((state) => ({
      ...state,
      items: [makeItem(0)],
      loading: false,
      loadItems: vi.fn().mockResolvedValue(undefined)
    }));

    getItemsMock.mockResolvedValueOnce([makeItem(4), makeItem(3)]).mockResolvedValueOnce([]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await screen.findByText('Brand 4');
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-14T10:30:00.000Z'));
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    fireEvent.click(screen.getByRole('button', { name: 'OK' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(getItemsMock).toHaveBeenLastCalledWith({
      limit: 4,
      createdSince: '2026-04-14T10:30:00.000Z'
    });
    expect(
      screen.getByText('Recent items cleared for this session. New uploads will appear here.')
    ).toBeInTheDocument();
    expect(window.localStorage.getItem('styleus:recent-cleared-since')).toBe('2026-04-14T10:30:00.000Z');
  });
});
