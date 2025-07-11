import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  isAdmin: boolean
}

interface AuthState {
  isAuthenticated: boolean
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<boolean>
  logout: () => void
  setUser: (user: User, token: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      user: null,
      token: null,

      login: async (email: string, password: string) => {
        try {
          const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
          })

          if (response.ok) {
            const data = await response.json()
            set({
              isAuthenticated: true,
              user: data.user,
              token: data.token,
            })
            return true
          }
          return false
        } catch (error) {
          console.error('Login error:', error)
          return false
        }
      },

      logout: () => {
        set({
          isAuthenticated: false,
          user: null,
          token: null,
        })
      },

      setUser: (user: User, token: string) => {
        set({
          isAuthenticated: true,
          user,
          token,
        })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user,
        token: state.token,
      }),
    }
  )
)
