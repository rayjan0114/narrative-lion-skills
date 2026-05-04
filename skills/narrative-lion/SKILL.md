---
name: narrative-lion
description: Interact with Narrative Lion — generate notes from YouTube, search your knowledge base, chat with notes, produce AI video shot pipelines, and export. Use when the user wants to "create a note from this video", "search my notes", "chat with my notes", "create a filmwork project", or "export my notes".
metadata:
  author: rayjan0114
  version: 0.5.0
---

# Narrative Lion

Base URL: `https://narrativelion.com`

## Auth

```
Authorization: Bearer $NLK_API_KEY
```

Create one at https://narrativelion.com/settings/api-keys (Pro plan required).

## API Reference

**MUST** `WebFetch https://narrativelion.com/docs` before your first API call in every conversation. Do NOT guess field names, argument names, or query names — the full schema is only in the docs.

## Endpoints (quick reference)

- **GraphQL** `POST /graphql` — notes, search, tags, collections, filmwork CRUD
- **REST** `GET /api/billing/usage` — credit usage and limits
- **REST** `POST /api/chat/stream` — SSE chat with notes (also film director + filmwork editing)
- **REST** `POST /api/export/request` — export notes as Markdown zip
- **REST** `POST /api/podcast/edit` — AI-edit podcast script
- **REST** `POST /api/podcast/sts` — speech-to-speech
- **REST** `POST /api/filmwork/director/persist` — persist storyboard + create filmwork note
- **REST** `POST /api/filmwork/director/generate-next` — batch-generate shot records from storyboard
- **REST** `POST /api/filmwork/director/refine` — stream revised storyboard (SSE)
- **REST** `POST /api/filmwork/director/refine-suggestions` — AI suggestions for storyboard
- **REST** `POST /api/threads/:threadId/active-note` — set active note on a chat thread

## Best Practices

### Collections

Two-level folder tree for organizing notes. Requires `notes:write` scope.

- Max 2 levels: top-level → one level of children. Set `parentId` on create to nest.
- `browseNotes(collectionId)` and `search(query, collectionId)` both accept `collectionId` for scoped results.
- `browseNotes(uncategorized: true)` returns notes not in any collection.
- Each `Note` includes `collections: [{ id, name, parentId, parentName }]`.

### Search

- `search(query)` is semantic — top result is usually correct even if the title doesn't match.
- `ftsSearch(query)` for exact keyword matching when semantic search returns irrelevant results.
- Both accept optional `collectionId` to scope results.

### Chat / SSE

- Chat stream event type is `"user_text"` (not "chat"). Payload field is `"text"` (not "message").
- Always use a fresh UUID for `actionId` — it's the idempotency key.
- `noteTypeScope: ["filmwork"]` in chat payload routes to filmwork edit. Without it → general chat.
- Thread must have active note set (`POST /threads/:threadId/active-note`) before filmwork chat editing.

### Filmwork

Two paths to create a project:

- **Path A: Film Director (AI-guided)** — chat stream with `activeTool: "film_director"` → persist → generate shots. Costs 2-3 credits.
- **Path B: Direct creation** — `createGeneralNote(noteType: "filmwork")` → set metadata → generate-next. Costs 0 + 1 credit/batch.

Key gotchas:
- `generate-next` requires `metadata.filmDirector` — without it: "Film Director setup not found".
- `generate-next` processes up to **10 shots per call** (batchSize capped at 10). Call repeatedly until `remainingShots` is 0.
- `INVALID_STORYBOARD_FORMAT` = no parseable `**01A** (Ns) — Title` line found.
- Film Director chat needs flat fields: `filmDirectorVideoType`, `filmDirectorTargetDurationSec`, `filmDirectorAspectRatio` (not a nested object).
- See `/docs/filmwork` for storyboard label format, direct creation workflow, and full payload details.

### Podcast

- `createGeneralNote(noteType: "podcast", skipAi: true)`: content must be podcast IR JSON (not plain markdown).

### Export

- Export zip: use `bsdtar -xf notes.zip -C notes/` — standard `unzip` mishandles non-ASCII filenames.

## HTTP Client

Prefer `curl` for API calls.
