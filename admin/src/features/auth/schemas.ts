import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('請輸入有效的 email'),
  password: z.string().min(1, '請輸入密碼'),
})

export type LoginValues = z.infer<typeof loginSchema>

export const forgotPasswordSchema = z.object({
  email: z.string().email('請輸入有效的 email'),
})

export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>

export const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(10, '密碼至少 10 個字元')
      .regex(/[A-Za-z]/, '密碼需含英文字母')
      .regex(/[0-9]/, '密碼需含數字'),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: '兩次輸入的密碼不一致',
    path: ['confirm_password'],
  })

export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>
