# CLAUDE.md (frontend)

Guidance specific to `frontend/`. See the [repo-root CLAUDE.md](../CLAUDE.md)
for the backend this talks to.

## What this is

A React 19 + TypeScript app (Vite, no UI framework) that's a pure client of
the backend's `/api/chat` and `/api/chat/stream` endpoints. Styled to look
and behave like chatgpt.com: dark theme, sidebar conversation list, message
bubbles, a composer with a streaming/chat mode toggle.

## Key design decisions

- **No backend URL config.** `src/api.ts` always calls same-origin `/api/*`.
  Dev: `vite.config.ts` proxies `/api` to `localhost:8000`. Prod (Docker):
  `nginx.conf` proxies `/api` to the `api` compose service. Don't
  reintroduce a hardcoded `http://localhost:8000` anywhere in `src/`.
- **SSE is parsed by hand** in `src/api.ts:streamChat`, not via
  `EventSource` — `EventSource` can't send a POST body, and `/api/chat/stream`
  requires one (the chat message). It reads `res.body`'s stream, splits on
  `\n\n` frame boundaries, and treats a bare `data: [DONE]` frame as
  end-of-stream (not JSON — don't try to `JSON.parse` it).
- **Conversation history is `localStorage`-only** (`src/hooks/useConversations.ts`).
  The backend has no "list conversations" or "get history" endpoint —
  Redis on the backend is the source of truth for the *agent's* memory
  (what the LLM sees), this is purely what the sidebar re-displays. If you
  add a backend history endpoint later, this hook is where you'd wire it in
  to hydrate a conversation on selection instead of (or in addition to)
  reading from storage.
- **`session_id` is per-conversation, not global.** A new conversation
  starts with `sessionId: null`; the first response's `session_id` is
  captured and reused for every later message in that conversation
  (`App.tsx:handleSend`). Passing `session_id: null` to the API is what
  makes it generate a fresh GUID server-side.
- **Stream/chat mode is a single global toggle** (`App.tsx`'s `streamMode`
  state), not per-conversation — matches how a mode toggle would read in
  the real ChatGPT UI (a session-wide setting, not per-thread).
- **Trace link**: `trace_url` from the API response (or first SSE event) is
  rendered as a "View trace ↗" link on assistant messages when present
  (`MessageBubble.tsx`). It's `null` whenever the backend has no Langfuse
  keys configured — always guard on it being non-null rather than assuming
  it's always present.

## Known gotcha already hit once

The streaming endpoint used to leak the tool call's raw JSON output into
the token stream ahead of the actual answer (a backend bug in
`app/api/routes.py`, since fixed — see the "Streaming" bullet in the root
CLAUDE.md). If assistant text ever looks like raw JSON is being prepended
again in stream mode, that's a backend regression, not a frontend parsing
bug — `src/api.ts` just forwards whatever `token` values the backend sends.

## Conventions

- Plain CSS (`src/index.css`), no Tailwind/styled-components/CSS-in-JS —
  keep it that way unless asked; the whole app is one stylesheet by design
  for a project this size.
- No icon library — icons are inline SVG in the component that uses them
  (see `Sidebar.tsx`, `Composer.tsx`, `MessageBubble.tsx`). Keep new icons
  the same way rather than adding an icon package for one glyph.
- `react-markdown` + `remark-gfm` render assistant messages (the backend's
  answers are markdown-formatted — bold labels, code blocks for raw
  METAR/TAF, bullet lists). User messages are rendered as plain text
  (`white-space: pre-wrap`), not markdown.
