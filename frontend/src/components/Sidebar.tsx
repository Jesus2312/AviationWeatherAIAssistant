import type { Conversation } from "../types"

interface SidebarProps {
  conversations: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}

function NewChatIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2m2 0-1 13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 7" />
    </svg>
  )
}

export function Sidebar({ conversations, activeId, onSelect, onNew, onDelete }: SidebarProps) {
  return (
    <aside className="sidebar">
      <button type="button" className="new-chat-button" onClick={onNew}>
        <NewChatIcon />
        New chat
      </button>

      <nav className="conversation-list" aria-label="Conversations">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conversation-item ${c.id === activeId ? "conversation-item-active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="conversation-title">{c.title}</span>
            <button
              type="button"
              className="conversation-delete"
              aria-label={`Delete "${c.title}"`}
              onClick={(e) => {
                e.stopPropagation()
                onDelete(c.id)
              }}
            >
              <TrashIcon />
            </button>
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">METAR/TAF Weather Assistant</div>
    </aside>
  )
}
