import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface MeUser {
  id: string
  name: string
  email: string
  role: string
  pending_email: string | null
  gender: string | null
  birthday: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<MeUser | null>(null)

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setUser(u: MeUser | null) {
    user.value = u
  }

  function clear() {
    user.value = null
  }

  return {
    user,
    isAuthenticated,
    isAdmin,
    setUser,
    clear,
  }
})
