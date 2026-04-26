---
name: narrative-lion
description: Interact with Narrative Lion — generate notes from YouTube, search your knowledge base, chat with notes, and export. Use when the user wants to "create a note from this video", "search my notes", "chat with my notes", or "export my notes".
metadata:
  author: rayjan0114
  version: 0.1.0
---

# Narrative Lion

Full API reference: https://narrativelion.com/docs

## Auth

All requests require an API key:

```
Authorization: Bearer $NL_API_KEY
```

Create one at https://narrativelion.com/settings/api-keys (Pro plan required).

## Endpoints

- **GraphQL** `POST /graphql` — submit jobs, query notes, search, manage tags
- **REST** `GET /api/notes/:id` — fetch a single note
- **REST** `POST /api/chat/stream` — SSE chat with your notes
- **REST** `POST /api/export/request` — export notes as Markdown zip

See the full API docs for request/response details, scopes, and curl examples.
