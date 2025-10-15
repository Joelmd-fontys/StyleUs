import { create } from 'zustand';
import { getItem, getItems, patchItem } from '../lib/api';
import { logger } from '../lib/logger';
import { WardrobeItem, WardrobeCategory } from '../domain/types';
import { PatchItemRequest } from '../domain/contracts';

export interface WardrobeFilters {
  category?: WardrobeCategory;
  q?: string;
}

interface WardrobeState {
  items: WardrobeItem[];
  loading: boolean;
  error?: string;
  filters: WardrobeFilters;
  selectedItemId?: string;
  loadItems: () => Promise<void>;
  setFilters: (filters: Partial<WardrobeFilters>) => Promise<void>;
  selectItem: (id?: string) => void;
  addItem: (item: WardrobeItem) => void;
  updateItem: (partial: Partial<WardrobeItem> & { id: string }) => void;
  replaceItem: (id: string, item: WardrobeItem) => void;
  refreshItem: (id: string) => Promise<void>;
  saveItem: (id: string, payload: PatchItemRequest) => Promise<WardrobeItem | undefined>;
}

export const useWardrobeStore = create<WardrobeState>((set, get) => ({
  items: [],
  loading: false,
  error: undefined,
  filters: {},
  selectedItemId: undefined,
  async loadItems() {
    const { filters } = get();
    set({ loading: true, error: undefined });
    try {
      const data = await getItems(filters);
      set({ items: data, loading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load wardrobe';
      set({ loading: false, error: message });
    }
  },
  async setFilters(partial) {
    const previous = get().filters;
    const next = { ...previous, ...partial };
    set({ filters: next });
    if (previous.category !== next.category || previous.q !== next.q) {
      await get().loadItems();
    }
  },
  selectItem(id) {
    set({ selectedItemId: id });
  },
  addItem(item) {
    set((state) => ({
      items: [item, ...state.items]
    }));
  },
  updateItem(partial) {
    set((state) => ({
      items: state.items.map((item) => (item.id === partial.id ? { ...item, ...partial } : item))
    }));
  },
  replaceItem(id, item) {
    set((state) => ({
      items: state.items.map((existing) => (existing.id === id ? item : existing))
    }));
  },
  async refreshItem(id) {
    try {
      const data = await getItem(id);
      get().replaceItem(id, data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to refresh item';
      set({ error: message });
    }
  },
  async saveItem(id, payload) {
    try {
      const updated = await patchItem(id, payload);
      get().replaceItem(id, updated);
      logger.itemEdited({ id });
      return updated;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to save item';
      set({ error: message });
      return undefined;
    }
  }
}));
