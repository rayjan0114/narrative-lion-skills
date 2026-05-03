---
name: narrative-lion
description: Interact with Narrative Lion — generate notes from YouTube, search your knowledge base, chat with notes, produce AI video shot pipelines, and export. Use when the user wants to "create a note from this video", "search my notes", "chat with my notes", "create a filmwork project", or "export my notes".
metadata:
  author: rayjan0114
  version: 0.4.0
---

# Narrative Lion

Base URL: `https://narrativelion.com`

## Auth

```
Authorization: Bearer $NLK_API_KEY
```

Create one at https://narrativelion.com/settings/api-keys (Pro plan required).

## API Reference

**MUST** `WebFetch https://narrativelion.com/docs` before your first API call in every conversation. Do NOT guess field names, argument names, or query names — the schema is only in the docs.

## Endpoints (quick reference)

- **GraphQL** `POST /graphql` — submit jobs, query/update notes, search, manage tags, filmwork CRUD
- **REST** `GET /api/billing/usage` — check credit usage and limits
- **REST** `POST /api/chat/stream` — SSE chat with your notes (also supports film director + filmwork editing)
- **REST** `POST /api/export/request` — export notes as Markdown zip
- **REST** `POST /api/podcast/edit` — AI-edit podcast script
- **REST** `POST /api/podcast/sts` — speech-to-speech
- **REST** `POST /api/filmwork/director/persist` — persist storyboard + create filmwork note
- **REST** `POST /api/filmwork/director/generate-next` — batch-generate shot records from storyboard
- **REST** `POST /api/filmwork/director/refine` — stream revised storyboard (SSE)
- **REST** `POST /api/filmwork/director/refine-suggestions` — get AI suggestions for storyboard
- **REST** `POST /api/filmwork/shots/edit` — AI shot editing (returns change diff)
- **REST** `POST /api/threads/:threadId/active-note` — set active note on a chat thread

## Filmwork — Shot Production Pipeline

Two paths to create a Filmwork project:

**Path A: Film Director (AI-guided)** — chat stream with `activeTool: "film_director"` → persist → generate shots. Costs 2-3 credits.

**Path B: Direct creation** — `createGeneralNote(noteType: "filmwork")` → set metadata → generate-next. Costs 0 + 1 credit/batch.

### Format gate

All filmwork note creation validates storyboard labels (`skipAi` is ignored):
- Labels parse correctly → **0 credits**, saved instantly
- Labels malformed but repairable → **1 credit**, AI auto-repairs
- No shot structure found → **rejected** with `INVALID_STORYBOARD_FORMAT`

### Storyboard label format

```markdown
**01A** (4s) — Shot title
Description body. Can be multiple lines.

**01B** (5s) — Second shot
More description.
```

Rules:
- Each shot: `**{2-3 digits}{one letter}{optional digit suffix}**` (bold)
- Duration in parentheses: `(4s)` or `(3.5s)`
- Em-dash + title on the same line
- Body text on following lines (until next label)
- Valid labels: 01A, 01B, 02A, 10C, 01A2

### Direct creation workflow

```
1. createGeneralNote(noteType: "filmwork", content: storyboard_md)
2. updateNote(noteId, metadata: ...) — set filmDirector setup (see docs for shape)
3. POST /api/filmwork/director/generate-next { noteId, batchSize }
```

Step 2 is REQUIRED — generate-next fails without `metadata.filmDirector`. See docs for exact JSON structure.

## Tips & Gotchas

- `search(query)` is semantic — top result is usually correct even if the title doesn't match your keywords.
- `ftsSearch(query)` for exact keyword matching when semantic search returns irrelevant results.
- Chat stream event type is `"user_text"` (not "chat"). Payload field is `"text"` (not "message").
- Always use a fresh UUID for `actionId` — it's the idempotency key.
- Export zip: use `bsdtar -xf notes.zip -C notes/` — standard `unzip` mishandles non-ASCII filenames.

### Podcast-specific

- `createGeneralNote(noteType: "podcast", skipAi: true)`: content must be podcast IR JSON (not plain markdown). System derives note_md from IR automatically.

### Filmwork-specific

- `noteTypeScope: ["filmwork"]` in chat payload routes to filmwork edit. Without it → general chat.
- Thread must have active note set before filmwork chat editing: `POST /threads/:threadId/active-note`.
- Film Director chat payload needs flat fields: `filmDirectorVideoType`, `filmDirectorTargetDurationSec`, `filmDirectorAspectRatio` (not a nested object).
- `POST /filmwork/shots/edit` with `shotLabel` scopes to one shot; omit for multi-shot.
- `generate-next` requires `metadata.filmDirector` — without it: "Film Director setup not found".
- `INVALID_STORYBOARD_FORMAT` = no parseable `**01A** (Ns) — Title` line found.
