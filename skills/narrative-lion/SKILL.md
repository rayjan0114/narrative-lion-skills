---
name: narrative-lion
description: Interact with Narrative Lion — generate notes from YouTube, search your knowledge base, chat with notes, produce AI video shot pipelines, and export. Use when the user wants to "create a note from this video", "search my notes", "chat with my notes", "create a filmwork project", or "export my notes".
metadata:
  author: rayjan0114
  version: 0.8.0
---

# Narrative Lion

Use the CLI at `${CLAUDE_PLUGIN_ROOT}/scripts/nl.py` for all API operations. Run via Bash:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py <command> [args...] [--json]
```

## Auth

```bash
export NLK_API_KEY=nlk_xxxxxxxx
```

Create one at https://narrativelion.com/settings/api-keys (Pro plan required).

## CLI Reference

### General

| Command | Description |
|---|---|
| `nl.py search <query> [--collection ID]` | Semantic search |
| `nl.py fts <query> [--collection ID]` | Full-text keyword search |
| `nl.py notes list [--collection ID] [--type T] [--uncategorized] [--starred]` | Browse notes |
| `nl.py notes get <noteId>` | Note detail |
| `nl.py notes create --type T --content C [--file path] [--skip-ai]` | Create note |
| `nl.py export <noteId> [noteId2 ...]` | Export as Markdown zip |
| `nl.py usage` | Credit usage |

### Filmwork

| Command | Description |
|---|---|
| `nl.py overview <noteId>` | Project overview: status counts + all shots |
| `nl.py shot <noteId> <label>` | Shot detail: preflight, assets, rolls, prompt |
| `nl.py preflight <noteId> <label>` | Preflight check only |
| `nl.py upload <shotId> <assetType> <file> [--label L]` | Upload asset (handles 3-step flow) |
| `nl.py upload-roll <shotId> <file> [--seed N --model M --prompt-version N]` | Upload roll video |
| `nl.py shot-update <shotId> --status S [--blocker JSON]` | Update shot status |
| `nl.py score <rollId> --face N --expr N --motion N --stability N --style N` | Score a roll (auto-computes weighted total) |
| `nl.py verdict <rollId> <approved\|rejected>` | Set roll verdict |
| `nl.py golden-roll <rollId>` | Set golden roll |
| `nl.py decision <noteId> [--shot ID] --action A --reason R --outcome O` | Log decision |
| `nl.py insight <noteId> --category C --title T --detail D [--source-shots JSON]` | Log insight |
| `nl.py decisions <noteId> [--shot ID]` | List decisions |
| `nl.py insights <noteId> [--category C]` | List insights |

All commands support `--json` for raw JSON output.

**Note:** `upload` and `upload-roll` take the shot **UUID** (the `id` field), not the label. Get the UUID from `nl.py shot <noteId> <label>`.

## Best Practices

### Search

`search` is semantic — finds results even when titles don't match.
`fts` is exact keyword matching. Both accept `--collection`.

### Collections

Two-level folder tree. `notes list --collection ID` scopes by collection.
`notes list --uncategorized` returns notes not in any collection.

### Chat / SSE (not yet in CLI)

For chat/SSE, use curl directly:
- Event type: `"user_text"` (not "chat"). Payload field: `"text"` (not "message").
- Fresh UUID for `actionId` every time — it's the idempotency key.
- `noteTypeScope: ["filmwork"]` routes to filmwork edit. Without it → general chat.
- Set active note on thread before filmwork editing.

Full REST endpoint docs: `WebFetch https://narrativelion.com/docs`

### Podcast

`notes create --type podcast --skip-ai --content <podcast-ir-json>`: content must be podcast IR JSON, not markdown.

---

## Filmwork Production

### Creating a Project

| Path | When | Cost |
|---|---|---|
| **A: Film Director** | Have concept, need storyboard | 1-2 credits |
| **B: Direct creation** | Have formatted storyboard | 0 credits |

**Path A:** Chat with `activeTool: "film_director"` → persist via `/api/filmwork/director/persist`.
**Path B:** `notes create --type filmwork --content <storyboard_md>` then create shots via GraphQL.

Labels must match `**01A** (Ns) — Title`. Invalid → `INVALID_STORYBOARD_FORMAT`.
Full field schemas: `WebFetch https://narrativelion.com/docs/filmwork`

### Agent Hold

`shot` output marks assets/rolls with `[HOLD]`. **If `[HOLD]`, skip that item.**

### Scanning Project State

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py overview <noteId>
```

Gives status counts + per-shot summary (assets, rolls, best score, preflight). Drill into a specific shot:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py shot <noteId> <label>
```

### Before Starting Work on a Shot

**Always check existing knowledge first:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py decisions <noteId> --shot <shotUUID>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py insights <noteId>
```

5 seconds of reading prevents 5 minutes of repeating past mistakes.

### The Production Loop

```
Prepare → Preflight → Generate → Review → Act on verdict
                                    ↑               |
                                    └───────────────┘
```

#### Prepare

1. Upload reference assets:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload <shotUUID> start_frame /path/to/frame.png
   ```
2. For collection types (keyframe, sfx, ref_image), use `--label`:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload <shotUUID> sfx /path/to/city_ambience.mp3 --label "City ambience"
   ```

#### Preflight

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py preflight <noteId> <label>
```

Three checks: `start_frame` ready, `audio` ready, `active_prompt` exists. **Do not generate until all pass.**

#### Generate & Upload

Generate video externally, then upload:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload-roll <shotUUID> /path/to/video.mp4 --seed 42 --model "kling-2.6" --prompt-version 1
```

#### Review & Score

Score across 5 weighted dimensions (max 55 points):

| Dimension | Flag | Weight |
|---|---|---|
| Face consistency | `--face` | x3 |
| Expression fidelity | `--expr` | x3 |
| Motion / morph | `--motion` | x2 |
| Stability | `--stability` | x2 |
| Style match | `--style` | x1 |

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py score <rollId> --face 4 --expr 3 --motion 4 --stability 4 --style 4
```

#### Act on Verdict

**>= 45 — Golden. Lock it:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py verdict <rollId> approved
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py golden-roll <rollId>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py decision <noteId> --shot <shotUUID> --action approve_golden --reason "scored 48, strong across all dimensions" --outcome "locked as golden, moving to next shot"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py shot-update <shotUUID> --status done
```

**40-44 — Approve with reservation:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py verdict <rollId> approved
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py golden-roll <rollId>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py decision <noteId> --shot <shotUUID> --action approve_with_reservation --reason "scored 42, minor hand drift at 6s" --outcome "approved, may revisit if stronger model becomes available"
```

**30-39 — Reject & revise:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py verdict <rollId> rejected
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py decision <noteId> --shot <shotUUID> --action plan_revision --reason "face morphing in last 2s" --outcome "adding negative prompt for morphing"
```
Then fix the prompt and re-roll. **Never re-roll without changing something.**

**< 30 — Reject & debug. Do not re-roll.** Follow playbook below.

### Logging Decisions and Insights

**Decisions** — log after every significant action:

Actions: `approve_golden`, `approve_with_reservation`, `plan_revision`, `switch_model`, `revise_prompt`, `block_shot`, `escalate_blocker`, `analyze_failure`, `strategy_change`.

**Insights** — log when you discover reusable knowledge:

Categories: `prompt`, `model`, `workflow`, `continuity`.

### Debug Playbooks

#### Roll scored < 30

1. **Do not re-roll.** Analyze first.
2. `nl.py decisions <noteId> --shot <shotUUID>` — what's been tried?
3. `nl.py insights <noteId> --category model` — known issues with this model?
4. Check scorecard — which dimension scored lowest? That's your fix target.
5. `nl.py overview <noteId>` — any done shots? Compare golden rolls' prompts.
6. Log: `nl.py decision <noteId> --shot <shotUUID> --action analyze_failure --reason "..." --outcome "plan: ..."`
7. Now fix and re-roll.

#### 3+ rejected rolls on same shot

**Stop. Do not re-roll.**

1. Collect all rolls' issues — find the common pattern.
2. `nl.py decisions <noteId> --shot <shotUUID>` — what's been tried so far?
3. `nl.py insights <noteId>` — is this pattern documented?
4. Consider: switch model, rewrite prompt, change reference frames, simplify the shot.
5. Log: `nl.py insight <noteId> --category workflow --title "..." --detail "Shot X required N attempts because..."`
6. Log: `nl.py decision <noteId> --shot <shotUUID> --action strategy_change --reason "..." --outcome "new approach: ..."`
7. Then try the new approach.

### Scoring Calibration

- 55/55 = perfect, extremely rare.
- 45+ = excellent. Lock it.
- Most first-run outputs land 35-42. Normal.
- Score the model against the brief, not the brief itself.
- BG mismatch between start/end frames = reference problem. Flag, don't penalize.
- Mouth never moves for scripted line = expected (lip-sync is post). Don't penalize.
- Mouth moves when it should be still = model failure ("liveliness bias"). Penalize under expression.
