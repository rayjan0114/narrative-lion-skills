---
name: narrative-lion
description: Interact with Narrative Lion — generate notes from YouTube, search your knowledge base, chat with notes, and export. Use when the user wants to "create a note from this video", "search my notes", "chat with my notes", or "export my notes".
metadata:
  author: rayjan0114
  version: 0.2.0
---

# Narrative Lion

Base URL: `https://narrativelion.com`

## Auth

```
Authorization: Bearer $NLK_API_KEY
```

Create one at https://narrativelion.com/settings/api-keys (Pro plan required).

## API Reference

Before making any API call, fetch the full docs for endpoint details, request/response schemas, and curl examples:

```
WebFetch https://narrativelion.com/docs
```

## Endpoints (quick reference)

- **GraphQL** `POST https://narrativelion.com/graphql` — submit jobs, query/update notes, search, manage tags
- **REST** `GET https://narrativelion.com/api/billing/usage` — check credit usage and limits
- **REST** `POST https://narrativelion.com/api/chat/stream` — SSE chat with your notes
- **REST** `POST https://narrativelion.com/api/export/request` — export notes as Markdown zip
- **REST** `POST https://narrativelion.com/api/podcast/edit` — AI-edit podcast script
- **REST** `POST https://narrativelion.com/api/podcast/sts` — speech-to-speech

## Tips

- When extracting an export zip, use `bsdtar -xf notes.zip -C notes/`. Standard `unzip` mishandles non-ASCII filenames.
