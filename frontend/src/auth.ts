const TOKEN_STORAGE_KEY = "auth_token"

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // localStorage unavailable (private browsing, etc.) -- the session
    // just won't survive a reload.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // ignore
  }
}

export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export async function login(payload: LoginPayload): Promise<string> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    if (res.status === 401) throw new Error("Invalid username or password.")
    throw new Error(`Login failed (HTTP ${res.status})`)
  }
  const body: LoginResponse = await res.json()
  return body.access_token
}
