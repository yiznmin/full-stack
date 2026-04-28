<script setup lang="ts">
import { ref } from 'vue'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { RouterLink } from 'vue-router'

import Card from '@/shared/ui/Card.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Button from '@/shared/ui/Button.vue'

import { forgotPasswordSchema } from '../schemas'
import { useForgotPasswordMutation } from '../queries'

const submitted = ref(false)
const apiError = ref<string | null>(null)

const forgot = useForgotPasswordMutation()

const { handleSubmit, errors, defineField, isSubmitting } = useForm({
  validationSchema: toTypedSchema(forgotPasswordSchema),
})

const [email, emailAttrs] = defineField('email')

const onSubmit = handleSubmit(async (values) => {
  apiError.value = null
  try {
    await forgot.mutateAsync(values.email)
    submitted.value = true
  } catch (e) {
    const err = e as { message?: string }
    apiError.value = err.message || '送出失敗，請稍後再試'
  }
})
</script>

<template>
  <Card>
    <h1 class="font-display text-ink-strong text-[22px] leading-[30px] mb-1">
      忘記密碼
    </h1>
    <p class="text-ink-muted text-[12px] mb-6">
      輸入登入 email，我們會寄出重設連結
    </p>

    <div
      v-if="apiError"
      class="mb-5 px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
      role="alert"
    >
      {{ apiError }}
    </div>

    <div
      v-if="submitted"
      class="border border-state-success/40 bg-[var(--color-state-success)]/[0.06] text-state-success px-3 py-3 rounded-[var(--radius-xs)] text-[13px] leading-relaxed"
    >
      若該帳號存在，重設連結已寄出。請至信箱收信（連結 1 小時內有效）。
    </div>

    <form v-else class="flex flex-col gap-3.5" novalidate @submit="onSubmit">
      <div>
        <Label for="forgot-email">Email</Label>
        <Input
          id="forgot-email"
          v-model="email"
          v-bind="emailAttrs"
          type="email"
          autocomplete="email"
          placeholder="admin@yiimui.com"
          :invalid="!!errors.email"
        />
        <p v-if="errors.email" class="mt-1 text-[12px] text-state-danger">
          {{ errors.email }}
        </p>
      </div>

      <Button type="submit" variant="primary" block :disabled="isSubmitting" class="mt-1">
        {{ isSubmitting ? '送出中…' : '寄送重設連結' }}
      </Button>
    </form>

    <div class="mt-5 pt-4 border-t border-line-hairline text-center">
      <RouterLink
        to="/admin/login"
        class="text-[13px] text-accent underline underline-offset-4 hover:text-accent-hover transition-colors duration-[120ms]"
      >
        ← 返回登入
      </RouterLink>
    </div>
  </Card>
</template>
