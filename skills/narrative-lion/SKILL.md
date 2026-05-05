---
name: narrative-lion
description: Interact with Narrative Lion — generate notes from YouTube, search your knowledge base, chat with notes, produce AI video shot pipelines, and export. Use when the user wants to "create a note from this video", "search my notes", "chat with my notes", "create a filmwork project", or "export my notes".
metadata:
  author: rayjan0114
  version: 0.7.0
---

# Narrative Lion

Base URL: `https://narrativelion.com`

## Auth

```
Authorization: Bearer $NLK_API_KEY
```

Create one at https://narrativelion.com/settings/api-keys (Pro plan required).

## API Reference

**MUST** fetch docs before your first API call in every conversation. Do NOT guess field names, argument names, or query names — the full schema is only in the docs.

- General tasks: `WebFetch https://narrativelion.com/docs`
- Filmwork tasks: `WebFetch https://narrativelion.com/docs/filmwork` (the main page has no filmwork schema)

## Endpoints (quick reference)

- `POST /graphql` — notes, search, tags, collections, filmwork CRUD
- `GET /api/billing/usage` — credit usage and limits
- `POST /api/chat/stream` — SSE chat (also film director + filmwork editing)
- `POST /api/export/request` — export notes as Markdown zip
- `POST /api/podcast/edit` — AI-edit podcast script
- `POST /api/podcast/sts` — speech-to-speech
- `POST /api/filmwork/director/persist` — persist storyboard + create filmwork note
- `POST /api/filmwork/director/refine` — stream revised storyboard (SSE)
- `POST /api/filmwork/director/refine-suggestions` — AI suggestions for storyboard
- `POST /api/threads/:threadId/active-note` — set active note on a chat thread

## Best Practices

### Collections

Two-level folder tree. Set `parentId` on create to nest (max 1 level deep).
`browseNotes(collectionId)` and `search(query, collectionId)` scope by collection.
`browseNotes(uncategorized: true)` returns notes not in any collection.

### Search

`search(query)` is semantic — usually finds what you need even when titles don't match.
`ftsSearch(query)` for exact keyword matching. Both accept optional `collectionId`.

### Chat / SSE

- Event type: `"user_text"` (not "chat"). Payload field: `"text"` (not "message").
- Fresh UUID for `actionId` every time — it's the idempotency key.
- `noteTypeScope: ["filmwork"]` routes to filmwork edit. Without it → general chat.
- Set active note on thread before filmwork editing.

### Podcast

`createGeneralNote(noteType: "podcast", skipAi: true)`: content must be podcast IR JSON, not markdown.

### Export

Use `bsdtar -xf notes.zip -C notes/` — standard `unzip` mishandles non-ASCII filenames.

---

## Filmwork Production

### Creating a Project

| Path | When | Cost |
|---|---|---|
| **A: Film Director** | Have concept, need storyboard | 1-2 credits |
| **B: Direct creation** | Have formatted storyboard | 0 credits |

**Path A:** Chat with `activeTool: "film_director"` → persist via `/api/filmwork/director/persist`.
**Path B:** `createGeneralNote(noteType: "filmwork", content: storyboard_md)` → `createFilmworkShot()` per shot.

Labels must match `**01A** (Ns) — Title`. Invalid → `INVALID_STORYBOARD_FORMAT`.
Film Director needs flat fields: `filmDirectorVideoType`, `filmDirectorTargetDurationSec`, `filmDirectorAspectRatio`.
Full field schemas at `/docs/filmwork`.

### Agent Hold

Rolls and assets have an `agentHold` boolean. **If `agentHold: true`, do not touch that item** — skip it. Always include `agentHold` when querying rolls/assets.

### Scanning Project State

Use `assetCounts` and `rollSummary` for compact overview — avoids pulling full asset/roll objects into context:

```graphql
{ filmworkOverview(noteId: "...") {
    statusCounts { notStarted assetPrep ready generating review done blocked }
    shots {
      shotId status
      assetCounts { startFrame endFrame keyframe dialogue sfx paddedAudio refVideo refImage total }
      rollSummary { total pending approved rejected bestScore goldenRollId }
      preflightStatus { ready }
    }
} }
```

Drill into full `assets`/`rolls` only when you need IDs for mutations (e.g. `setGoldenAsset`, `deleteRoll`).

**ID gotcha:** `shotId` in overview responses is the human label (e.g. "01A"). But `filmworkShot(shotId)` and all mutations take the **UUID** (the `id` field). Use `filmworkShotByLabel(noteId, shotLabel)` when you have a label.

### Before Starting Work on a Shot

**Always check existing knowledge first:**

```graphql
{ filmworkDecisions(noteId: "...", shotId: "...") { action reason outcome createdAt } }
{ filmworkInsights(noteId: "...") { category title detail } }
```

5 seconds of reading prevents 5 minutes of repeating past mistakes. Decisions and insights accumulate across sessions — they are the project's memory.

### The Production Loop

```
Prepare → Preflight → Generate → Review → Act on verdict
                                    ↑               |
                                    └───────────────┘
```

#### Prepare

1. Upload reference assets: `requestUploadUrl(shotId, assetType, filename)` → PUT file → `confirmAssetUpload(...)`.
   **PUT requires the same `Authorization: Bearer` header as GraphQL calls** (not a presigned URL).
2. Set direction, prompt, model config via `createFilmworkShot` or `updateFilmworkShot`.
3. For dialogue shots: upload `dialogue` or `padded_audio` asset.

#### Preflight

```graphql
{ filmworkShotByLabel(noteId: "...", shotLabel: "01A") { preflightStatus { ready checks { name passed detail } } } }
```

Three checks must pass: `start_frame` ready, `audio` ready, `active_prompt` exists. **Do not generate until `ready: true`.**

If blocked externally → `updateShotStatus(shotId, status: "blocked", blockerJson: "{\"description\":\"...\",\"action\":\"...\",\"createdAt\":\"...\"}")`.

#### Generate & Upload

Generate video externally, then: `requestRollUploadUrl` → PUT video → `confirmRollUpload(shotId, rollKey, seed, modelUsed, promptVersion)`.

#### Review & Score

Score across 5 weighted dimensions (max 55 points):

| Dimension | ID | Weight | Focus |
|---|---|---|---|
| Face consistency | `faceLikeness` | x3 | Identity stable across all frames |
| Expression fidelity | `expression` | x3 | Performance matches intended emotion |
| Motion / morph | `motionNatural` | x2 | Hands, fingers, props hold structure |
| Stability | `stability` | x2 | No late-stage collapse or drift |
| Style match | `styleMatch` | x1 | Visual style consistent throughout |

```graphql
mutation {
  scoreRoll(rollId: "...", scorecardJson: "{\"rubricVersion\":1,\"scores\":{\"faceLikeness\":4,\"expression\":3,\"motionNatural\":4,\"stability\":4,\"styleMatch\":4}}")
  { id totalScore }
}
```

#### Act on Verdict

**>= 45 — Golden. Lock it:**
```
updateRollVerdict(rollId, verdict: "approved")
setGoldenRoll(rollId)
addDecision(noteId, shotId, actor: "agent", action: "approve_golden",
  reason: "scored 48, strong across all dimensions",
  outcome: "locked as golden, moving to next shot")
updateShotStatus(shotId, status: "done")
```

**40-44 — Approve with reservation:**
```
updateRollVerdict(rollId, verdict: "approved")
setGoldenRoll(rollId)
addDecision(..., action: "approve_with_reservation",
  reason: "scored 42, minor hand drift at 6s",
  outcome: "approved, may revisit if stronger model becomes available")
```

**30-39 — Reject & revise:**
```
updateRollVerdict(rollId, verdict: "rejected")
```
`updateRollVerdict(rejected)` auto-logs a basic rejection. Now add your analysis:
```
addDecision(..., actor: "agent", action: "plan_revision",
  reason: "face morphing in last 2s, expression too flat at beat 2",
  outcome: "adding negative prompt for morphing, restructuring beat timing")
```
Then fix the prompt and re-roll. **Never re-roll without changing something** — same inputs = same result.

**< 30 — Reject & debug. Do not re-roll.** Follow "Roll scored < 30" playbook below.

### Logging Decisions and Insights

**Decisions** record what happened and why. Log after every significant action:

`addDecision(noteId, shotId?, actor: "agent", action, reason, outcome)`

Actions: `"approve_golden"`, `"approve_with_reservation"`, `"plan_revision"`, `"switch_model"`, `"revise_prompt"`, `"block_shot"`, `"escalate_blocker"`, `"analyze_failure"`, `"strategy_change"`.

**Insights** capture reusable knowledge. Log when you discover something that applies beyond the current shot:

`addInsight(noteId, category, title, detail?, sourceShotsJson?, applicableToJson?)`

Categories: `prompt` (what works in prompts), `model` (capabilities and limits), `workflow` (process lessons), `continuity` (cross-shot consistency).

Example: after discovering a model limitation:
```
addInsight(noteId: "...", category: "model",
  title: "Kling 2.6 cannot reverse facing direction during push-in",
  detail: "Character must change facing direction during camera push-in — consistently produces face morph. Works fine with locked or lateral camera.",
  sourceShotsJson: "[\"01A\", \"03B\"]")
```

Example: after finding a prompt pattern that works:
```
addInsight(noteId: "...", category: "prompt",
  title: "Beat structure improves close-up acting",
  detail: "Timed beats (Beat 1: 0-2s action, Beat 2: 2-4s reaction) produce more precise expressions than free-form description.",
  sourceShotsJson: "[\"01B\"]",
  applicableToJson: "[\"all close-ups with dialogue\"]")
```

**Link reference material** when you use external notes (character bibles, production specs, etc.):

`addNoteLink(sourceNoteId, targetNoteId, linkType)` — types: `character`, `setting`, `story`, `continuation`.

### Debug Playbooks

#### Roll scored < 30

1. **Do not re-roll.** Analyze first.
2. `filmworkDecisions(noteId, shotId)` — what's been tried?
3. `filmworkInsights(noteId, category: "model")` — known issues with this model?
4. Check `scorecardJson` — which dimension scored lowest? That's your fix target.
5. `filmworkOverview(noteId)` — any `done` shots? Compare golden rolls' prompts.
6. Log analysis: `addDecision(action: "analyze_failure", reason: "...", outcome: "plan: ...")`.
7. Now fix and re-roll.

#### 3+ rejected rolls on same shot

**Stop. Do not re-roll.**

1. Collect all rolls' `issues` — find the common pattern.
2. `filmworkDecisions(noteId, shotId)` — what's been tried so far?
3. `filmworkInsights(noteId)` — is this pattern documented?
4. Consider: switch model, rewrite prompt from scratch, change reference frames, simplify the shot.
5. Log the pattern: `addInsight(category: "workflow", title: "...", detail: "Shot X required N attempts because...")`.
6. Log your new plan: `addDecision(action: "strategy_change", reason: "...", outcome: "new approach: ...")`.
7. Then try the new approach.

#### Shot blocked

1. Check `blockerJson` for the description and required action.
2. Can you resolve it? Fix it → `updateShotStatus(status: "asset_prep")`.
3. Cannot? → `addDecision(action: "escalate_blocker", outcome: "needs human input")` → move to next shot.

#### Same model failing on a shot type

1. `filmworkInsights(noteId, category: "model")` — already documented?
2. If not: `addInsight(category: "model", title: "[Model] struggles with [type]", detail: "...", sourceShotsJson: "[...]")`.
3. Check if another model succeeded on similar shots in this project.
4. `addDecision(action: "switch_model", reason: "...", outcome: "switching to ...")`.

### Scoring Calibration

- 55/55 = perfect execution, zero drift. Extremely rare.
- 45+ = excellent. Lock it.
- Most first-run outputs land 35-42. This is normal.
- Score the model against the brief, not the brief itself. Wrong emotion = creative decision issue, not model failure.
- BG mismatch between start/end frames = reference problem. Flag it, don't penalize the model.
- Props missing from output = they weren't in the input frames. Fix the setup, not the prompt.
- Mouth never moves for scripted line = expected for models without native audio. Lip-sync is a post step. Don't penalize.
- Mouth moves continuously when it should be still = model failure ("liveliness bias"). Penalize under expression.

## JSON Field Quick Reference

Several mutation fields accept stringified JSON. Common gotchas:

- **`dialogue`**: must be a JSON **array** `[{speaker, text, type, emotion?}]`, not a string. Empty = `[]`.
- **`blockerJson`**: single **object** `{description, action, createdAt}`, not an array.
- **`promptsJson`**: array `[{version (Int), body, isActive (Bool), ...}]`. Exactly one entry should have `isActive: true`.
- **`seed`** and **`promptVersion`** on `confirmRollUpload`: both are **`Int`**, not `String`.

Full schemas with examples at `/docs/filmwork` → "JSON field schemas" section.

## HTTP Client

- Always set a `User-Agent` header (e.g. `User-Agent: NarrativeLion-Agent/1.0`). Default UAs from Python/Node HTTP libraries are blocked → `403`.
- If you get `403 Invalid origin` without an API key, add `Origin: https://narrativelion.com`.
