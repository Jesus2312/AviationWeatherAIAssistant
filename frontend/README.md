# Aviation Weather Assistant -- Frontend

A React + TypeScript chat UI for the [METAR/TAF weather assistant API](../README.md),
styled after chatgpt.com: dark theme, sidebar with conversation history, and
a composer with a mode toggle for the API's two response modes.

## Features

- **Chat mode** (`POST /api/chat`) -- waits for the full reply.
- **Stream mode** (`POST /api/chat/stream`, default) -- renders tokens as
  they arrive via Server-Sent Events.
- Sidebar conversation history, persisted in `localStorage` (one browser
  only -- the backend has no "list past conversations" endpoint; Redis is
  the source of truth for the agent's own memory, this is purely for
  re-displaying what the UI already showed you).
- Markdown rendering (tables, code blocks, lists) for decoded METAR/TAF
  responses.
- A "View trace" link under each assistant reply, linking to that request's
  Langfuse trace (hidden if the backend has no Langfuse keys configured).

## Setup

```bash
npm install
npm run dev
```

Opens on `http://localhost:5173`. The dev server proxies `/api/*` to
`http://localhost:8000` (see `vite.config.ts`) -- start the backend first
(see the [repo root README](../README.md)), or point the proxy elsewhere
with `VITE_API_PROXY_TARGET=http://your-backend:8000 npm run dev`.

## Build

```bash
npm run build   # type-checks then outputs static files to dist/
npm run preview # serve the production build locally
```

A production build expects to be served from the same origin as the API
(or behind a reverse proxy that forwards `/api/*` to it) -- `src/api.ts`
calls same-origin relative paths, no build-time backend URL needed.

## Structure

```
src/
  api.ts                 fetch wrappers for /api/chat and /api/chat/stream
                          (hand-rolled SSE parsing -- EventSource can't POST)
  types.ts                ChatMessage / Conversation types
  hooks/useConversations.ts   localStorage-backed conversation list + messages
  components/
    Sidebar.tsx            conversation list, new/delete
    ChatWindow.tsx          message list + empty-state suggestions
    MessageBubble.tsx        one message (markdown for assistant replies)
    Composer.tsx             input box, stream/chat mode toggle, send
  App.tsx                 wires it together; owns the actual send/stream call
```
