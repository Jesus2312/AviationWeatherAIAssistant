export type Role = "user" | "assistant"

export interface ChatMessage {
  id: string
  role: Role
  content: string
  /** Present on assistant messages once the request settles. */
  traceId?: string
  traceUrl?: string | null
  /** True while an assistant message is still streaming/waiting. */
  pending?: boolean
  /** Set if the request failed (circuit breaker open, network error, ...). */
  error?: string
}

export interface Conversation {
  id: string
  /** == the backend session_id; null until the first response assigns one. */
  sessionId: string | null
  title: string
  createdAt: number
  messages: ChatMessage[]
}
