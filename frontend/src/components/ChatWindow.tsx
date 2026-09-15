import { useEffect, useRef } from "react"
import type { Conversation } from "../types"
import { MessageBubble } from "./MessageBubble"

const SUGGESTIONS = [
  "What's the current METAR for KJFK?",
  "Give me the TAF forecast for El Paso International",
  "Decode this: KELP 121953Z 00000KT 10SM CLR 28/09 A3005",
  "Is KLAX currently VFR or IFR?",
]

interface ChatWindowProps {
  conversation: Conversation
  onSuggestion: (text: string) => void
}

export function ChatWindow({ conversation, onSuggestion }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [conversation.messages])

  if (conversation.messages.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon" aria-hidden="true">
          ✈
        </div>
        <h1>Aviation Weather Assistant</h1>
        <p>Ask about current METAR observations or TAF forecasts for any airport.</p>
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="suggestion-card" onClick={() => onSuggestion(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="message-list">
      {conversation.messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
