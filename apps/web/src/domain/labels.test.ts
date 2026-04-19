import { describe, expect, it } from 'vitest';
import {
  ATTRIBUTE_LABELS,
  CATEGORY_LABELS,
  MATERIAL_LABELS,
  SUBCATEGORY_LABELS as BACKEND_SUBCATEGORY_LABELS,
  STYLE_LABELS
} from './generated/taxonomy';
import {
  FILTER_CATEGORY_OPTIONS,
  ITEM_DETAIL_CATEGORY_OPTIONS,
  SUBCATEGORY_LABELS,
  UPLOAD_REVIEW_CATEGORY_OPTIONS,
  getSubcategories,
  toDisplayLabel
} from './labels';

describe('taxonomy adapter', () => {
  it('keeps frontend category options aligned with the backend taxonomy', () => {
    expect(CATEGORY_LABELS).toEqual(['top', 'bottom', 'shoes', 'outerwear', 'accessory']);
    expect(FILTER_CATEGORY_OPTIONS).toEqual([
      { label: 'All', value: undefined },
      { label: 'Tops', value: 'top' },
      { label: 'Bottoms', value: 'bottom' },
      { label: 'Outerwear', value: 'outerwear' },
      { label: 'Shoes', value: 'shoes' },
      { label: 'Accessories', value: 'accessory' },
      { label: 'Uncategorized', value: 'uncategorized' }
    ]);
    expect(ITEM_DETAIL_CATEGORY_OPTIONS).toEqual([
      'top',
      'bottom',
      'outerwear',
      'shoes',
      'accessory',
      'unknown',
      'uncategorized'
    ]);
    expect(UPLOAD_REVIEW_CATEGORY_OPTIONS).toEqual(['top', 'bottom', 'outerwear', 'shoes', 'accessory', 'uncategorized']);
  });

  it('keeps subcategory groupings and display helpers stable', () => {
    expect(SUBCATEGORY_LABELS).toEqual({
      top: [...BACKEND_SUBCATEGORY_LABELS.top],
      bottom: [...BACKEND_SUBCATEGORY_LABELS.bottom],
      shoes: [...BACKEND_SUBCATEGORY_LABELS.shoes],
      outerwear: [...BACKEND_SUBCATEGORY_LABELS.outerwear],
      accessory: [...BACKEND_SUBCATEGORY_LABELS.accessory],
      unknown: [],
      uncategorized: []
    });
    expect(getSubcategories('top')).toEqual(BACKEND_SUBCATEGORY_LABELS.top);
    expect(getSubcategories('uncategorized')).toEqual([]);
    expect(toDisplayLabel('rain jacket')).toBe('Rain Jacket');
    expect(toDisplayLabel('slim-fit')).toBe('Slim-Fit');
    expect(STYLE_LABELS).toEqual(['casual', 'streetwear', 'formal', 'sporty', 'outdoor', 'minimal', 'vintage', 'retro', 'heritage']);
    expect(MATERIAL_LABELS).toEqual(['cotton', 'denim', 'wool', 'leather', 'nylon', 'knit', 'fleece', 'suede', 'mesh', 'canvas', 'linen']);
    expect(ATTRIBUTE_LABELS).toEqual(['oversized', 'slim-fit', 'relaxed', 'tailored', 'cropped', 'quilted', 'chunky', 'boxy']);
  });
});
