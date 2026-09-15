import { useCallback, useEffect, useRef, useState } from "react"
import type { ChatMessage, Conversation } from "../types"

const STORAGE_KEY = "metar-chat.conversations.v1"

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Conversation[]
    if (!Array.isArray(parsed)) return []
    return parsed
  } catch {
    return []
  }
}

function makeTitle(firstMessage: string): string {
  const trimmed = firstMessage.trim().replace(/\s+/g, " ")
  if (trimmed.length <= 48) return trimmed || "New chat"
  return `${trimmed.slice(0, 48)}…`
}

function newConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    sessionId: null,
    title: "New chat",
    createdAt: Date.now(),
    messages: [],
  }
}

/**
 * Persists conversations (and their locally-rendered message history) in
 * localStorage, keyed per browser. The backend is the source of truth for
 * agent *memory* (Redis, keyed by session_id) -- this is purely what the UI
 * re-displays when you click back into a past conversation, since the API
 * has no "fetch conversation history" endpoint.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const loaded = loadConversations()
    return loaded.length > 0 ? loaded : [newConversation()]
  })
  const [activeId, setActiveId] = useState<string>(() => conversations[0].id)

  // Avoid persisting on the very first render (we just loaded from storage).
  const isFirstRun = useRef(true)
  useEffect(() => {
    if (isFirstRun.current) {
      isFirstRun.current = false
      return
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
  }, [conversations])

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  const startNewConversation = useCallback(() => {
    const conv = newConversation()
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
    return conv.id
  }, [])

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id)
        return next.length > 0 ? next : [newConversation()]
      })
      setActiveId((current) => {
        if (current !== id) return current
        const remaining = conversations.filter((c) => c.id !== id)
        return remaining[0]?.id ?? conversations[0].id
      })
    },
    [conversations],
  )

  const addMessage = useCallback((conversationId: string, message: ChatMessage) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== conversationId) return c
        const messages = [...c.messages, message]
        const title =
          c.messages.length === 0 && message.role === "user"
            ? makeTitle(message.content)
            : c.title
        return { ...c, messages, title }
      }),
    )
  }, [])

  const updateMessage = useCallback(
    (conversationId: string, messageId: string, patch: Partial<ChatMessage>) => {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== conversationId) return c
          return {
            ...c,
            messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
          }
        }),
      )
    },
    [],
  )

  const setSessionId = useCallback((conversationId: string, sessionId: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === conversationId ? { ...c, sessionId } : c)),
    )
  }, [])

  return {
    conversations,
    active,
    activeId,
    setActiveId,
    startNewConversation,
    deleteConversation,
    addMessage,
    updateMessage,
    setSessionId,
  }
}
