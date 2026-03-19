import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WardrobeItem } from '../domain/types';
import { useWardrobeStore } from '../store/wardrobe';
import UploadReviewPage from './UploadReviewPage';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock
  };
});

const mockItem: WardrobeItem = {
  id: 'item-temp',
  imageUrl: '/image.jpg',
  thumbUrl: '/image.jpg',
  mediumUrl: '/image.jpg',
  category: 'shoes',
  subcategory: 'sneakers',
  color: 'Black',
  primaryColor: 'Black',
  secondaryColor: 'Gray',
  brand: 'Mock',
  createdAt: new Date().toISOString(),
  tags: ['streetwear', 'leather'],
  imageMetadata: undefined,
  aiConfidence: 0.84
};

const mockAI = {
  category: 'shoes',
  subcategory: 'sneakers',
  primaryColor: 'black',
  secondaryColor: 'gray',
  materials: ['mesh'],
  styleTags: ['streetwear'],
  tags: ['streetwear', 'leather'],
  confidence: 0.84,
  categoryConfidence: 0.84,
  subcategoryConfidence: 0.73,
  primaryColorConfidence: 0.7,
  secondaryColorConfidence: 0.4
};

const mockUncertainAI = {
  ...mockAI,
  uncertain: true,
  uncertainFields: ['category']
};

const mockPendingAI = {
  ...mockAI,
  pending: true,
  job: {
    id: 'job-1',
    status: 'running',
    attempts: 1,
    createdAt: new Date().toISOString(),
    pending: true
  }
};

const baseState = useWardrobeStore.getState();

describe('UploadReviewPage', () => {
  beforeEach(() => {
    navigateMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    useWardrobeStore.setState(baseState, true);
  });

  const renderPage = async () => {
    await act(async () => {
      render(
        <MemoryRouter
          initialEntries={[`/upload/review/${mockItem.id}`]}
          future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
        >
          <Routes>
            <Route path="/upload/review/:id" element={<UploadReviewPage />} />
          </Routes>
        </MemoryRouter>
      );
    });
  };

  it('accepts AI predictions and saves item', async () => {
    const saveItemMock = vi.fn().mockResolvedValue(mockItem);
    const loadItemsMock = vi.fn().mockResolvedValue(undefined);
    const showFlashMessageMock = vi.fn();

    useWardrobeStore.setState((state) => ({
      ...state,
      uploadReview: {
        item: mockItem,
        ai: mockAI,
        loading: false,
        isConfirming: false,
        error: undefined
      },
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      hydrateUploadReview: vi.fn().mockResolvedValue(undefined),
      saveItem: saveItemMock,
      deleteItem: vi.fn().mockResolvedValue(true),
      clearUploadReview: vi.fn(),
      loadItems: loadItemsMock,
      showFlashMessage: showFlashMessageMock
    }));

    await renderPage();

    const acceptButton = await screen.findByRole('button', { name: /accept predictions/i });
    await act(async () => {
      fireEvent.click(acceptButton);
    });

    await waitFor(() => expect(saveItemMock).toHaveBeenCalledTimes(1));
    expect(saveItemMock).toHaveBeenCalledWith(
      mockItem.id,
      expect.objectContaining({
        category: 'shoes',
        subcategory: 'sneakers',
        primaryColor: 'black',
        secondaryColor: 'gray',
        brand: 'Mock'
      })
    );
    expect(loadItemsMock).toHaveBeenCalled();
    expect(showFlashMessageMock).toHaveBeenCalledWith('Item added successfully');
    expect(navigateMock).toHaveBeenCalledWith('/wardrobe');
  });

  it('allows editing predictions before confirm', async () => {
    const saveItemMock = vi.fn().mockResolvedValue({
      ...mockItem,
      primaryColor: 'Midnight Blue',
      tags: ['edited', 'custom']
    });
    const loadItemsMock = vi.fn().mockResolvedValue(undefined);
    const showFlashMessageMock = vi.fn();

    useWardrobeStore.setState((state) => ({
      ...state,
      uploadReview: {
        item: mockItem,
        ai: mockAI,
        loading: false,
        isConfirming: false,
        error: undefined
      },
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      hydrateUploadReview: vi.fn().mockResolvedValue(undefined),
      saveItem: saveItemMock,
      deleteItem: vi.fn().mockResolvedValue(true),
      clearUploadReview: vi.fn(),
      loadItems: loadItemsMock,
      showFlashMessage: showFlashMessageMock
    }));

    await renderPage();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /edit & confirm/i }));
    });

    const primaryColorInput = screen.getByLabelText(/primary color/i) as HTMLInputElement;
    const subcategorySelect = screen.getByLabelText(/subcategory/i) as HTMLSelectElement;
    const brandInput = screen.getByPlaceholderText(/e\.g\./i);
    const tagsInput = screen.getByLabelText(/tags/i);

    await act(async () => {
      fireEvent.change(primaryColorInput, { target: { value: 'Midnight Blue' } });
      fireEvent.change(subcategorySelect, { target: { value: 'boots' } });
      fireEvent.change(brandInput, { target: { value: 'Edited Brand' } });
      fireEvent.change(tagsInput, { target: { value: 'edited, custom' } });
      fireEvent.click(screen.getByRole('button', { name: /confirm changes/i }));
    });

    await waitFor(() => expect(saveItemMock).toHaveBeenCalledTimes(1));
    expect(saveItemMock).toHaveBeenCalledWith(
      mockItem.id,
      expect.objectContaining({
        subcategory: 'boots',
        primaryColor: 'Midnight Blue',
        tags: ['edited', 'custom'],
        brand: 'Edited Brand'
      })
    );
    expect(loadItemsMock).toHaveBeenCalled();
    expect(showFlashMessageMock).toHaveBeenCalledWith('Item added successfully');
    expect(navigateMock).toHaveBeenCalledWith('/wardrobe');
  });

  it('shows a loading overlay while AI predictions are pending', async () => {
    useWardrobeStore.setState((state) => ({
      ...state,
      uploadReview: {
        item: mockItem,
        ai: undefined,
        loading: true,
        isConfirming: false,
        error: undefined
      },
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      hydrateUploadReview: vi.fn().mockResolvedValue(undefined),
      saveItem: vi.fn().mockResolvedValue(mockItem),
      deleteItem: vi.fn().mockResolvedValue(true),
      clearUploadReview: vi.fn(),
      loadItems: vi.fn().mockResolvedValue(undefined),
      showFlashMessage: vi.fn()
    }));

    await renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Analyzing your item/i)).toBeInTheDocument();
    });
  });

  it('blocks interaction while pending results are still polling', async () => {
    useWardrobeStore.setState((state) => ({
      ...state,
      uploadReview: {
        item: { ...mockItem, aiJob: mockPendingAI.job },
        ai: mockPendingAI,
        loading: false,
        isConfirming: false,
        error: undefined
      },
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      hydrateUploadReview: vi.fn().mockResolvedValue(undefined),
      saveItem: vi.fn().mockResolvedValue(mockItem),
      deleteItem: vi.fn().mockResolvedValue(true),
      clearUploadReview: vi.fn(),
      loadItems: vi.fn().mockResolvedValue(undefined),
      showFlashMessage: vi.fn()
    }));

    await renderPage();

    expect(screen.getByText(/Analyzing your item/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /Reading image features|Estimating garment shape|Detecting color signals|Ranking category matches|Preparing suggestions/i
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/This usually takes a few seconds/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit & confirm/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /accept predictions/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
  });

  it('shows a longer-running loading message when pending AI exceeds the expected window', async () => {
    const delayedPendingAI = {
      ...mockPendingAI,
      job: {
        ...mockPendingAI.job,
        createdAt: new Date(Date.now() - 60_000).toISOString(),
        startedAt: new Date(Date.now() - 55_000).toISOString()
      }
    };

    useWardrobeStore.setState((state) => ({
      ...state,
      uploadReview: {
        item: { ...mockItem, aiJob: delayedPendingAI.job },
        ai: delayedPendingAI,
        loading: false,
        isConfirming: false,
        error: undefined
      },
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      hydrateUploadReview: vi.fn().mockResolvedValue(undefined),
      saveItem: vi.fn().mockResolvedValue(mockItem),
      deleteItem: vi.fn().mockResolvedValue(true),
      clearUploadReview: vi.fn(),
      loadItems: vi.fn().mockResolvedValue(undefined),
      showFlashMessage: vi.fn()
    }));

    await renderPage();

    expect(screen.getByText(/Still running the AI pipeline/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /edit & confirm/i })).toBeDisabled();
  });

  it('uses a single review banner without repeated check badges', async () => {
    useWardrobeStore.setState((state) => ({
      ...state,
      uploadReview: {
        item: mockItem,
        ai: mockUncertainAI,
        loading: false,
        isConfirming: false,
        error: undefined
      },
      fetchUploadReviewAI: vi.fn().mockResolvedValue(undefined),
      hydrateUploadReview: vi.fn().mockResolvedValue(undefined),
      saveItem: vi.fn().mockResolvedValue(mockItem),
      deleteItem: vi.fn().mockResolvedValue(true),
      clearUploadReview: vi.fn(),
      loadItems: vi.fn().mockResolvedValue(undefined),
      showFlashMessage: vi.fn()
    }));

    await renderPage();

    expect(screen.getByText(/Review recommended for category/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Check$/)).not.toBeInTheDocument();
  });
});
