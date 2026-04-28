<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import Card from '@/shared/ui/Card.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Button from '@/shared/ui/Button.vue'

import { resetPasswordSchema } from '../schemas'
import { useResetPasswordMutation } from '../queries'

const route = useRoute()
const router = useRouter()

const token = computed(() => (route.query.token as string) || '')
const submitted = ref(false)
const apiError = ref<string | null>(null)

const { handleSubmit, errors, defineField, isSubmitting } = useForm({
  validationSchema: toTypedSchema(resetPasswordSchema),
})

const [newPassword, newPasswordAttrs] = defineField('new_password')
const [confirmPassword, confirmPasswordAttrs] = defineField('confirm_password')

onMounted(() => {
  if (!token.value) {
    router.replace('/admin/login')
  }
})

const reset = useResetPasswordMutation()

const onSubmit = handleSubmit(async (values) => {
  apiError.value = null
  try {
    await reset.mutateAsync({
      token: token.value,
      newPassword: values.new_password,
    })
    submitted.value = true
    setTimeout(() => router.push('/admin/login'), 3000)
  } catch (e) {
    const err = e as { status?: number; message?: string }
    if (err.status === 400) {
      apiError.value = '連結已過期或無效，請重新申請'
    } else {
      apiError.value = err.message || '更新失敗，請稍後再試'
    }
  }
})
</script>

<template>
  <Card>
    <h1 class="font-display text-ink-strong text-[22px] leading-[30px] mb-1">
      設定新密碼
    </h1>
    <p class="text-ink-muted text-[12px] mb-6">
      請輸入新的密碼。完成後會自動跳回登入頁。
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
      密碼已更新。3 秒後跳回登入頁⋯
    </div>

    <form v-else class="flex flex-col gap-3.5" novalidate @submit="onSubmit">
      <div>
        <Label for="reset-new">新密碼</Label>
        <Input
          id="reset-new"
          v-model="newPassword"
          v-bind="newPasswordAttrs"
          type="password"
          autocomplete="new-password"
          :invalid="!!errors.new_password"
        />
        <p
          v-if="errors.new_password"
          class="mt-1 text-[12px] text-state-danger"
        >
          {{ errors.new_password }}
        </p>
        <p v-else class="mt-1 text-[11px] text-ink-muted">
          至少 10 個字元，需含英文字母與數字
        </p>
      </div>

      <div>
        <Label for="reset-confirm">再次輸入</Label>
        <Input
          id="reset-confirm"
          v-model="confirmPassword"
          v-bind="confirmPasswordAttrs"
          type="password"
          autocomplete="new-password"
          :invalid="!!errors.confirm_password"
        />
        <p
          v-if="errors.confirm_password"
          class="mt-1 text-[12px] text-state-danger"
        >
          {{ errors.confirm_password }}
        </p>
      </div>

      <Button type="submit" variant="primary" block :disabled="isSubmitting" class="mt-1">
        {{ isSubmitting ? '更新中…' : '更新密碼' }}
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
