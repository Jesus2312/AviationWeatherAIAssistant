import { getToken } from "./auth"

export class UnauthorizedError extends Error {
  constructor() {
    super("Session expired. Please log in again.")
    this.name = "UnauthorizedError"
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface ChatRequestPayload {
  message: string
  session_id?: string | null
}

export interface ChatResponsePayload {
  answer: string
  session_id: string
  trace_id: string
  trace_url: string | null
}

export interface StreamEvent {
  session_id?: string
  trace_id?: string
  trace_url?: string | null
  token?: string
  error?: string
}

// Same-origin: the Vite dev server proxies /api to the FastAPI backend (see
// vite.config.ts), and a production build is expected to be served from the
// same origin as the API (or behind a reverse proxy that forwards /api).
const API_BASE = ""

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body?.detail === "string") return body.detail
  } catch {
    // response wasn't JSON; fall through to the generic message
  }
  return `Request failed (HTTP ${res.status})`
}

export async function sendChat(payload: ChatRequestPayload): Promise<ChatResponsePayload> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  })
  if (res.status === 401) throw new UnauthorizedError()
  if (!res.ok) {
    throw new Error(await readErrorDetail(res))
  }
  return res.json()
}

/**
 * POSTs to /api/chat/stream and invokes `onEvent` for each SSE data frame
 * as it arrives. EventSource can't be used here since it doesn't support
 * POST bodies, so the response stream is parsed by hand.
 */
export async function streamChat(
  payload: ChatRequestPayload,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
    signal,
  })
  if (res.status === 401) throw new UnauthorizedError()
  if (!res.ok || !res.body) {
    throw new Error(await readErrorDetail(res))
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) return
    buffer += decoder.decode(value, { stream: true })

    let separatorIndex: number
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)

      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n")
      if (!data) continue
      if (data === "[DONE]") return

      try {
        onEvent(JSON.parse(data) as StreamEvent)
      } catch {
        // malformed frame; skip it rather than crash the whole stream
      }
    }
  }
}
