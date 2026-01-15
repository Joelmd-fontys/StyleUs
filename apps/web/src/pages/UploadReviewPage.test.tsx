import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Route, Routes, MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import UploadReviewPage from './UploadReviewPage';
import { useWardrobeStore } from '../store/wardrobe';
import { WardrobeItem } from '../domain/types';

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

const baseState = useWardrobeStore.getState();

describe('UploadReviewPage', () => {
  afterEach(() => {
    useWardrobeStore.setState(baseState, true);
    navigateMock.mockReset();
  });

  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={[`/upload/review/${mockItem.id}`]}>
        <Routes>
          <Route path="/upload/review/:id" element={<UploadReviewPage />} />
        </Routes>
      </MemoryRouter>
    );

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

    renderPage();

    const acceptButton = await screen.findByRole('button', { name: /accept predictions/i });
    fireEvent.click(acceptButton);

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

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /edit & confirm/i }));

    const primaryColorInput = screen.getByLabelText(/primary color/i) as HTMLInputElement;
    fireEvent.change(primaryColorInput, { target: { value: 'Midnight Blue' } });

    const subcategorySelect = screen.getByLabelText(/subcategory/i) as HTMLSelectElement;
    fireEvent.change(subcategorySelect, { target: { value: 'boots' } });

    const brandInput = screen.getByPlaceholderText(/e\.g\./i);
    fireEvent.change(brandInput, { target: { value: 'Edited Brand' } });

    const tagsInput = screen.getByPlaceholderText(/streetwear, leather/i);
    fireEvent.change(tagsInput, { target: { value: 'edited, custom' } });

    fireEvent.click(screen.getByRole('button', { name: /confirm changes/i }));

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

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Analyzing your item/i)).toBeInTheDocument();
    });
  });
});
