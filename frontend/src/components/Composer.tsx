import { useEffect, useRef, useState } from "react"
import type { KeyboardEvent } from "react"

interface ComposerProps {
  disabled: boolean
  streamMode: boolean
  onToggleStreamMode: () => void
  onSend: (text: string) => void
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  )
}

export function Composer({ disabled, streamMode, onToggleStreamMode, onSend }: ComposerProps) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [value])

  const submit = () => {
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue("")
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="composer-wrap">
      <div className="composer">
        <textarea
          ref={textareaRef}
          className="composer-input"
          placeholder="Message the aviation weather assistant..."
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="composer-toolbar">
          <button
            type="button"
            className={`mode-toggle ${streamMode ? "mode-toggle-on" : ""}`}
            onClick={onToggleStreamMode}
            title="Toggle streaming responses"
          >
            <span className="mode-toggle-dot" />
            Stream
          </button>
          <button
            type="button"
            className="send-button"
            disabled={disabled || !value.trim()}
            onClick={submit}
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        </div>
      </div>
      <div className="composer-hint">
        {streamMode ? "Streaming mode — tokens arrive as they're generated." : "Chat mode — waits for the full reply."}{" "}
        Enter to send, Shift+Enter for a new line.
      </div>
    </div>
  )
}
