import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { ChatMessage } from "../types"

function UserAvatar() {
  return (
    <div className="avatar avatar-user" aria-hidden="true">
      U
    </div>
  )
}

function AssistantAvatar() {
  return (
    <div className="avatar avatar-assistant" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M12 2 3 7v10l9 5 9-5V7z" />
        <path d="M3 7l9 5 9-5M12 12v10" />
      </svg>
    </div>
  )
}

function TypingIndicator() {
  return (
    <span className="typing-indicator" aria-label="Assistant is typing">
      <span />
      <span />
      <span />
    </span>
  )
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user"
  const showTyping = message.pending && !message.content && !message.error

  return (
    <div className={`message-row ${isUser ? "message-row-user" : "message-row-assistant"}`}>
      {isUser ? <UserAvatar /> : <AssistantAvatar />}
      <div className="message-body">
        {isUser ? (
          <div className="bubble bubble-user">{message.content}</div>
        ) : (
          <div className="bubble bubble-assistant">
            {showTyping ? (
              <TypingIndicator />
            ) : (
              <div className="markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              </div>
            )}
            {message.error && <div className="message-error">{message.error}</div>}
            {message.traceUrl && !message.pending && (
              <a
                className="trace-link"
                href={message.traceUrl}
                target="_blank"
                rel="noreferrer"
                title={message.traceId}
              >
                View trace ↗
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
