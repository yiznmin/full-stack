<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { RouterLink } from 'vue-router'

import Card from '@/shared/ui/Card.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Button from '@/shared/ui/Button.vue'

import { useRouter } from 'vue-router'

import { loginSchema } from '../schemas'
import { useLoginMutation } from '../queries'
import { useAuthStore } from '../store'

const formError = ref<string | null>(null)
const flash = ref<string | null>(null)

onMounted(() => {
  // 從 sessionStorage 取出 guard 留下的 flash（例：「此帳號非管理員」）
  const f = sessionStorage.getItem('auth_flash')
  if (f) {
    flash.value = f
    sessionStorage.removeItem('auth_flash')
  }
})

const login = useLoginMutation()
const auth = useAuthStore()
const router = useRouter()

const isDevBypass =
  import.meta.env.DEV && import.meta.env.VITE_DEV_BYPASS_AUTH === 'true'

const { handleSubmit, errors, defineField, isSubmitting } = useForm({
  validationSchema: toTypedSchema(loginSchema),
})

const [email, emailAttrs] = defineField('email')
const [password, passwordAttrs] = defineField('password')

const onSubmit = handleSubmit(async (values) => {
  formError.value = null
  flash.value = null

  // DEV bypass：不打 API，直接假登入跳 dashboard
  if (isDevBypass) {
    auth.setUser({
      id: 'dev-admin',
      name: '易木 Dev',
      email: values.email,
      role: 'admin',
      pending_email: null,
      gender: null,
      birthday: null,
    })
    router.push('/admin/dashboard')
    return
  }

  try {
    await login.mutateAsync(values)
  } catch (e) {
    const err = e as { status?: number; message?: string }
    if (err.status === 401) {
      formError.value = '帳號或密碼錯誤'
    } else if (err.status === 403) {
      formError.value = '此帳號非管理員'
    } else {
      formError.value = err.message || '登入失敗，請稍後再試'
    }
  }
})
</script>

<template>
  <Card>
    <h1 class="font-display text-ink-strong text-[22px] leading-[30px] mb-0.5">
      登入工坊
    </h1>
    <p class="text-ink-muted text-[12px] mb-5">
      管理員專用入口
    </p>

    <div
      v-if="flash"
      class="mb-5 px-3 py-2 border border-state-warning/40 bg-[var(--color-state-warning)]/[0.06] text-state-warning text-[13px] rounded-[var(--radius-xs)]"
    >
      {{ flash }}
    </div>

    <div
      v-if="formError"
      class="mb-5 px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
      role="alert"
    >
      {{ formError }}
    </div>

    <form class="flex flex-col gap-3.5" novalidate @submit="onSubmit">
      <div>
        <Label for="login-email">Email</Label>
        <Input
          id="login-email"
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

      <div>
        <Label for="login-password">密碼</Label>
        <Input
          id="login-password"
          v-model="password"
          v-bind="passwordAttrs"
          type="password"
          autocomplete="current-password"
          placeholder="輸入密碼"
          :invalid="!!errors.password"
        />
        <p v-if="errors.password" class="mt-1 text-[12px] text-state-danger">
          {{ errors.password }}
        </p>
      </div>

      <Button type="submit" variant="primary" block :disabled="isSubmitting" class="mt-1">
        {{ isSubmitting ? '登入中…' : '登入' }}
      </Button>
    </form>

    <div class="mt-5 pt-4 border-t border-line-hairline text-center">
      <RouterLink
        to="/admin/forgot-password"
        class="text-[13px] text-accent underline underline-offset-4 hover:text-accent-hover transition-colors duration-[120ms]"
      >
        忘記密碼？
      </RouterLink>
    </div>
  </Card>
</template>
