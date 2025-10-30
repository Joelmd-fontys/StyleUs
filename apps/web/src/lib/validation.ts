import { z } from 'zod';
import { WardrobeCategory } from '../domain/types';

export const wardrobeCategorySchema = z.enum([
  'top',
  'bottom',
  'outerwear',
  'shoes',
  'accessory',
  'unknown'
] as [WardrobeCategory, ...WardrobeCategory[]]);

export const wardrobeItemEditSchema = z.object({
  category: wardrobeCategorySchema,
  color: z.string().trim().min(1, 'Color is required'),
  brand: z
    .string()
    .trim()
    .max(60, 'Brand must be 60 characters or fewer')
    .optional()
    .or(z.literal(''))
    .transform((value) => (value === '' ? undefined : value)),
  tags: z
    .array(z.string().trim().min(1, 'Tag cannot be empty'))
    .optional()
    .default([])
});

export type WardrobeItemEditInput = z.infer<typeof wardrobeItemEditSchema>;
