import { create, type StoreApi, type UseBoundStore } from 'zustand';
import { deleteItem as deleteItemRequest, getItem, getItems, getItemAIPreview, patchItem } from '../lib/api';
import { USE_LIVE_API_ITEMS } from '../lib/config';
import { logger } from '../lib/logger';
import { WardrobeItem, WardrobeCategory } from '../domain/types';
import { PatchItemRequest, AIPreviewResponse } from '../domain/contracts';
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

interface FlashMessage {
  type: 'success' | 'error';
  message: string;
}

interface UploadReviewContext {
  item?: WardrobeItem;
  ai?: AIPreviewResponse | null;
  loading: boolean;
  error?: string;
  isConfirming: boolean;
}

interface WardrobeState {
  items: WardrobeItem[];
  loading: boolean;
  error?: string;
  filters: WardrobeFilters;
  selectedItemId?: string;
  uploadReview?: UploadReviewContext;
  flashMessage?: FlashMessage;
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
  prepareUploadReview: (item: WardrobeItem) => void;
  setUploadReviewAI: (ai: AIPreviewResponse | null) => void;
  setUploadReviewLoading: (loading: boolean) => void;
  setUploadReviewError: (message?: string) => void;
  clearUploadReview: () => void;
  fetchUploadReviewAI: (id: string) => Promise<void>;
  setUploadReviewConfirming: (flag: boolean) => void;
  showFlashMessage: (message: string, type?: FlashMessage['type']) => void;
  clearFlashMessage: () => void;
  hydrateUploadReview: (id: string) => Promise<void>;
}

export type WardrobeStore = UseBoundStore<StoreApi<WardrobeState>>;

const deriveAIPreviewFromItem = (item: WardrobeItem): AIPreviewResponse => ({
  category: item.ai?.category ?? item.category,
  subcategory: item.ai?.subcategory ?? item.subcategory ?? null,
  categoryConfidence: item.ai?.confidence ?? item.aiConfidence ?? null,
  subcategoryConfidence: null,
  primaryColor: item.primaryColor ?? null,
  primaryColorConfidence: null,
  secondaryColor: item.secondaryColor ?? null,
  secondaryColorConfidence: null,
  materials: item.ai?.materials ?? [],
  styleTags: item.ai?.styleTags ?? [],
  tags: item.tags,
  confidence: item.ai?.confidence ?? item.aiConfidence ?? null
});

export const useWardrobeStore: WardrobeStore = create<WardrobeState>((set, get) => ({
  items: [],
  loading: false,
  error: undefined,
  filters: {},
  selectedItemId: undefined,
  uploadReview: undefined,
  flashMessage: undefined,
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
    get().setUploadReviewConfirming(true);
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
          category: payload.category ?? existing.category,
          subcategory: payload.subcategory ?? existing.subcategory
        });
      }
      get().replaceItem(id, updated);
      logger.itemEdited({ id });
      const currentReview = get().uploadReview;
      if (currentReview?.item && currentReview.item.id === id) {
        set({
          uploadReview: {
            ...currentReview,
            item: updated,
            ai: deriveAIPreviewFromItem(updated),
            loading: false,
            isConfirming: false,
            error: undefined
          }
        });
      }
      return updated;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to save item';
      set({ error: message });
      return undefined;
    } finally {
      get().setUploadReviewConfirming(false);
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
      const message = error instanceof Error ? error.message : 'Unable to delete item';
      set({
        items: previousItems,
        selectedItemId: previousSelected,
        error: message
      });
      logger.itemDeleted({ id, error: message });
      return false;
    }
  },
  prepareUploadReview(item) {
    set({
      uploadReview: {
        item,
        ai: undefined,
        loading: true,
        isConfirming: false,
        error: undefined
      }
    });
  },
  setUploadReviewAI(ai) {
    set((state) =>
      state.uploadReview
        ? {
            uploadReview: {
              ...state.uploadReview,
              ai,
              loading: false,
              error: undefined
            }
          }
        : state
    );
  },
  setUploadReviewLoading(loading) {
    set((state) =>
      state.uploadReview
        ? {
            uploadReview: {
              ...state.uploadReview,
              loading
            }
          }
        : state
    );
  },
  setUploadReviewError(message) {
    set((state) =>
      state.uploadReview
        ? {
            uploadReview: {
              ...state.uploadReview,
              error: message,
              loading: false
            }
          }
        : state
    );
  },
  clearUploadReview() {
    set({ uploadReview: undefined });
  },
  async fetchUploadReviewAI(id: string) {
    if (!USE_LIVE_API_ITEMS) {
      const item = mockFindWardrobeItem(id);
      if (item) {
        set((state) =>
          state.uploadReview
            ? {
                uploadReview: {
                  ...state.uploadReview,
                  ai: deriveAIPreviewFromItem(item),
                  loading: false,
                  error: undefined
                }
              }
            : state
        );
      }
      return;
    }

    set((state) =>
      state.uploadReview
        ? {
            uploadReview: {
              ...state.uploadReview,
              loading: true,
              error: undefined
            }
          }
        : state
    );
    try {
      const ai = await getItemAIPreview(id);
      get().setUploadReviewAI(ai);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to fetch AI preview';
      get().setUploadReviewError(message);
    }
  },
  setUploadReviewConfirming(flag) {
    set((state) =>
      state.uploadReview
        ? {
            uploadReview: {
              ...state.uploadReview,
              isConfirming: flag
            }
          }
        : state
    );
  },
  showFlashMessage(message, type = 'success') {
    set({ flashMessage: { message, type } });
  },
  clearFlashMessage() {
    set({ flashMessage: undefined });
  },
  async hydrateUploadReview(id: string) {
    try {
      const existing = get().items.find((item) => item.id === id);
      let item = existing;
      if (!item) {
        item = USE_LIVE_API_ITEMS ? await getItem(id) : mockFindWardrobeItem(id);
      }
      if (!item) {
        throw new Error('Item not found');
      }
      set({
        uploadReview: {
          item,
          ai: get().uploadReview?.ai,
          loading: false,
          error: undefined,
          isConfirming: false
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load upload review';
      set({
        uploadReview: {
          item: get().uploadReview?.item as WardrobeItem,
          ai: get().uploadReview?.ai,
          loading: false,
          error: message,
          isConfirming: false
        }
      });
    }
  }
}));
