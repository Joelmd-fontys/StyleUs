import { create, type StoreApi, type UseBoundStore } from 'zustand';
import { deleteItem as deleteItemRequest, getItem, getItems, patchItem } from '../lib/api';
import { USE_LIVE_API_ITEMS } from '../lib/config';
import { logger } from '../lib/logger';
import { WardrobeItem, WardrobeCategory } from '../domain/types';
import { PatchItemRequest } from '../domain/contracts';
import {
  findWardrobeItem as mockFindWardrobeItem,
  getWardrobeItems as mockGetWardrobeItems,
  removeWardrobeItem as mockRemoveWardrobeItem,
  saveWardrobeItem as mockSaveWardrobeItem
} from '../mocks/fixtures';

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
  removeItem: (id: string) => void;
  deleteItem: (id: string) => Promise<boolean>;
}

export type WardrobeStore = UseBoundStore<StoreApi<WardrobeState>>;

export const useWardrobeStore: WardrobeStore = create<WardrobeState>((set, get) => ({
  items: [],
  loading: false,
  error: undefined,
  filters: {},
  selectedItemId: undefined,
  async loadItems() {
    const { filters } = get();
    set({ loading: true, error: undefined });
    try {
      const data = USE_LIVE_API_ITEMS ? await getItems(filters) : mockGetWardrobeItems();
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
      const data = USE_LIVE_API_ITEMS ? await getItem(id) : mockFindWardrobeItem(id);
      if (!data) {
        throw new Error('Item not found');
      }
      get().replaceItem(id, data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to refresh item';
      set({ error: message });
    }
  },
  async saveItem(id, payload) {
    try {
      let updated: WardrobeItem;
      if (USE_LIVE_API_ITEMS) {
        updated = await patchItem(id, payload);
      } else {
        const existing = mockFindWardrobeItem(id);
        if (!existing) {
          throw new Error('Item not found');
        }
        updated = mockSaveWardrobeItem({
          ...existing,
          ...payload,
          tags: payload.tags ?? existing.tags,
          brand: payload.brand ?? existing.brand,
          color: payload.color ?? existing.color,
          category: payload.category ?? existing.category
        });
      }
      get().replaceItem(id, updated);
      logger.itemEdited({ id });
      return updated;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to save item';
      set({ error: message });
      return undefined;
    }
  },
  removeItem(id) {
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
      selectedItemId: state.selectedItemId === id ? undefined : state.selectedItemId
    }));
  },
  async deleteItem(id) {
    const previousItems = get().items;
    const previousSelected = get().selectedItemId;
    set({ error: undefined });
    get().removeItem(id);

    try {
      if (USE_LIVE_API_ITEMS) {
        await deleteItemRequest(id);
      } else {
        mockRemoveWardrobeItem(id);
      }
      logger.itemDeleted({ id });
      return true;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to delete item';
      set({
        items: previousItems,
        selectedItemId: previousSelected,
        error: message
      });
      logger.itemDeleted({ id, error: message });
      return false;
    }
  }
}));
