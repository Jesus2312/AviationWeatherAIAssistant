import { useState } from "react"
import { UnauthorizedError, sendChat, streamChat } from "./api"
import { ChatWindow } from "./components/ChatWindow"
import { Composer } from "./components/Composer"
import { Login } from "./components/Login"
import { Sidebar } from "./components/Sidebar"
import { useAuth } from "./hooks/useAuth"
import { useConversations } from "./hooks/useConversations"
import type { ChatMessage } from "./types"

export default function App() {
  const { isAuthenticated, login, logout } = useAuth()
  const {
    conversations,
    active,
    activeId,
    setActiveId,
    startNewConversation,
    deleteConversation,
    addMessage,
    updateMessage,
    setSessionId,
  } = useConversations()

  const [streamMode, setStreamMode] = useState(true)
  const [isSending, setIsSending] = useState(false)

  async function handleSend(text: string) {
    const conversationId = active.id
    const sessionId = active.sessionId

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    }
    addMessage(conversationId, userMessage)

    const assistantId = crypto.randomUUID()
    addMessage(conversationId, {
      id: assistantId,
      role: "assistant",
      content: "",
      pending: true,
    })

    setIsSending(true)
    try {
      if (streamMode) {
        let content = ""
        let gotSessionId = false
        await streamChat({ message: text, session_id: sessionId }, (event) => {
          if (event.session_id && !gotSessionId) {
            gotSessionId = true
            if (!sessionId) setSessionId(conversationId, event.session_id)
          }
          if (event.token) {
            content += event.token
            updateMessage(conversationId, assistantId, { content, pending: true })
          }
          if (event.trace_id) {
            updateMessage(conversationId, assistantId, {
              traceId: event.trace_id,
              traceUrl: event.trace_url ?? null,
            })
          }
          if (event.error) {
            updateMessage(conversationId, assistantId, { error: event.error })
          }
        })
        updateMessage(conversationId, assistantId, { pending: false })
      } else {
        const res = await sendChat({ message: text, session_id: sessionId })
        if (!sessionId) setSessionId(conversationId, res.session_id)
        updateMessage(conversationId, assistantId, {
          content: res.answer,
          pending: false,
          traceId: res.trace_id,
          traceUrl: res.trace_url,
        })
      }
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        logout()
        return
      }
      updateMessage(conversationId, assistantId, {
        pending: false,
        error: err instanceof Error ? err.message : "Something went wrong.",
      })
    } finally {
      setIsSending(false)
    }
  }

  if (!isAuthenticated) {
    return <Login onLogin={login} />
  }

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={startNewConversation}
        onDelete={deleteConversation}
      />
      <main className="main-panel">
        <header className="main-header">
          <span>METAR/TAF Weather Assistant</span>
          <button type="button" className="logout-button" onClick={logout}>
            Log out
          </button>
        </header>
        <div className="main-scroll">
          <ChatWindow conversation={active} onSuggestion={handleSend} />
        </div>
        <Composer
          disabled={isSending}
          streamMode={streamMode}
          onToggleStreamMode={() => setStreamMode((v) => !v)}
          onSend={handleSend}
        />
      </main>
    </div>
  )
}
