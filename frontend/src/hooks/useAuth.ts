import { useCallback, useState } from "react"
import { clearToken, getToken, login as loginRequest, setToken } from "../auth"

export function useAuth() {
  const [token, setTokenState] = useState<string | null>(() => getToken())

  const login = useCallback(async (username: string, password: string) => {
    const accessToken = await loginRequest({ username, password })
    setToken(accessToken)
    setTokenState(accessToken)
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setTokenState(null)
  }, [])

  return { token, isAuthenticated: token !== null, login, logout }
}
