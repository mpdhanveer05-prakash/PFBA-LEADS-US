import { useState, useCallback } from 'react'
import { setToken as setApiToken } from '../api/client'

interface AuthUser {
  username: string
  role: string
}

const TOKEN_KEY = 'pf_token'
const USER_KEY  = 'pf_user'

function readToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

function readUser(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

// Restore token into axios on every module load (page refresh)
const _restoredToken = readToken()
if (_restoredToken) setApiToken(_restoredToken)

export function useAuth() {
  const [token, setTokenState] = useState<string | null>(readToken)
  const [user, setUserState] = useState<AuthUser | null>(readUser)

  const login = useCallback((t: string, u: AuthUser) => {
    sessionStorage.setItem(TOKEN_KEY, t)
    sessionStorage.setItem(USER_KEY, JSON.stringify(u))
    setApiToken(t)
    setTokenState(t)
    setUserState(u)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    setApiToken(null)
    setTokenState(null)
    setUserState(null)
  }, [])

  return { token, user, login, logout }
}
