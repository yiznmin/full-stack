import { z } from 'zod'

export const productSchema = z.object({
  title: z.string().min(1, '請輸入商品名稱').max(100, '不超過 100 字'),
  description: z.string().max(2000, '不超過 2000 字'),
  cover_image_url: z.string().url('請上傳封面圖'),
  series_id: z.string().uuid().nullable(),
  series_order: z.number().int().min(0),
  status: z.enum(['draft', 'on_sale', 'off_sale']),
  is_featured: z.boolean(),
  tag_ids: z.array(z.string().uuid()),
})
export type ProductFormValues = z.infer<typeof productSchema>

export const variantSchema = z.object({
  production_job_id: z.string().uuid('請選擇 production job'),
  price: z.number().int().min(1).max(99999),
})
export type VariantFormValues = z.infer<typeof variantSchema>

export const seriesSchema = z.object({
  name: z.string().min(1, '請輸入名稱').max(50),
  description: z.string().max(500).nullable(),
})
export type SeriesFormValues = z.infer<typeof seriesSchema>

export const tagSchema = z.object({
  name: z.string().min(1, '請輸入標籤').max(20),
})
export type TagFormValues = z.infer<typeof tagSchema>
