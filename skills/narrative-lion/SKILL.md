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

All API calls use `Authorization: Bearer $NLK_API_KEY` header.

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

### Film Director

| Command | Description |
|---|---|
| `nl.py director <concept> [--type T] [--duration N] [--aspect R] [--style S]` | Generate storyboard from concept (costs 1-2 credits) |
| `nl.py director-persist <threadId> --storyboard <md> --instruction <text>` | Persist storyboard as filmwork note (no LLM cost) |

### Filmwork

| Command | Description |
|---|---|
| `nl.py overview <noteId>` | Project overview: status counts + all shots |
| `nl.py shot <noteId> <label>` | Shot detail: preflight, assets, rolls, prompt |
| `nl.py preflight <noteId> <label>` | Preflight check only |
| `nl.py upload <shotId> <assetType> <file> [--label L] [--method M --model M --prompt P --user-note N --parent JSON]` | Upload asset (handles 3-step flow, optional provenance) |
| `nl.py upload-roll <shotId> <file> [--seed N --model M --prompt-version N]` | Upload roll video |
| `nl.py shot-update <shotId> [--status S] [--blocker JSON] [--prompts JSON] [--dialogue JSON] [--direction JSON] [--model-config JSON] [--relations JSON] [--duration N]` | Update shot status and/or fields |
| `nl.py score <rollId> --face N --expr N --motion N --stability N --style N` | Score a roll (auto-computes weighted total) |
| `nl.py verdict <rollId> <approved\|rejected>` | Set roll verdict |
| `nl.py golden-roll <rollId>` | Set golden roll |
| `nl.py decision <noteId> [--shot ID] --action A --reason R --outcome O` | Log decision |
| `nl.py insight <noteId> --category C --title T --detail D [--source-shots JSON]` | Log insight |
| `nl.py decisions <noteId> [--shot ID] [--limit N] [--offset N]` | List decisions |
| `nl.py insights <noteId> [--category C] [--limit N] [--offset N]` | List insights (default 50) |
| `nl.py provenance <assetId>` | Query how an asset was made |
| `nl.py lineage <assetId> [--depth N]` | Query full lineage DAG |
| `nl.py roll-snapshot <rollId>` | What asset versions were used to generate a roll |
| `nl.py set-provenance <assetId> --method M [--model M] [--prompt P] [--parent JSON ...]` | Set/update provenance after the fact |
| `nl.py download <assetId> <output_path>` | Download a single asset to local file |
| `nl.py download-shot <noteId> <label> [--dir D] [--all]` | Download golden assets for a shot (--all for every version) |

All commands support `--json` for raw JSON output.

**Note:** `upload` and `upload-roll` take the shot **UUID** (the `id` field), not the label. Get the UUID from `nl.py shot <noteId> <label>`.

## Best Practices

### Search

`search` is semantic — finds results even when titles don't match.
`fts` is exact keyword matching. Both accept `--collection`.

### Collections

Two-level folder tree. `notes list --collection ID` scopes by collection.
`notes list --uncategorized` returns notes not in any collection.

### Chat / SSE

### Film Director Notes

`director` costs 1-2 credits per call.

Threading: omit `--thread` for a new conversation, pass `--thread <id>` to continue.

### Podcast

`notes create --type podcast --skip-ai --content <podcast-ir-json>`: content must be podcast IR JSON, not markdown.

---

## Filmwork Production

### Creating a Project

| Path | When | Cost |
|---|---|---|
| **A: Film Director** | Have concept, need storyboard | 1-2 credits |
| **B: Direct creation** | Have formatted storyboard | 0 credits |

**Path A:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py director "concept description" --type animate --duration 30 --aspect 16:9
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py director-persist <threadId> --storyboard <md> --instruction "concept" --type animate --duration 30 --aspect 16:9
```

**Path B:** `notes create --type filmwork --content <storyboard_md>` then create shots via GraphQL.

Labels must match `**01A** (Ns) — Title`. Invalid → `INVALID_STORYBOARD_FORMAT`.

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

### Sync to Local Studio

Download golden assets to the local studio directory:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py download-shot <noteId> <label> --dir studio/scene/season01/ep01/final/<label>_<scene>/
```

Studio directory convention: `studio/scene/season01/ep01/final/{label}_{scene_name}/`

File naming: `{label}_FINAL_start_frame.png`, `{label}_FINAL_end_frame.png`, `{label}_SFX_{name}.mp3`, etc.

### Before Starting Work on a Shot

**Always check existing knowledge first:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py decisions <noteId> --shot <shotUUID>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py insights <noteId>
```

5 seconds of reading prevents 5 minutes of repeating past mistakes.

### Before Writing or Updating Prompts

Spawn a sub-agent (via the Agent tool) to review relevant insights before writing or modifying a video prompt. This avoids loading raw insight data into the main context.

Sub-agent instructions:
1. Run `nl.py insights <noteId> --category prompt --json`
2. Read through all returned insights
3. Return a short bullet list of insights relevant to the current shot's content (camera movement, character action, scene type)
4. If no insights are relevant, return "No relevant prompt insights found"

Do the same with `--category model` if switching models or debugging a failed roll.

### The Production Loop

```
Prepare → Preflight → Generate → Review → Act on verdict
                                    ↑               |
                                    └───────────────┘
```

#### Prepare

1. Upload reference assets with provenance:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload <shotUUID> start_frame /path/to/frame.png \
     --method ai_generated --model "gpt-image-2" --prompt "Winter city street..." \
     --parent '{"assetId":"<prev-asset-id>","role":"base"}' \
     --parent '{"externalRef":"claire_fullbody.png — LoRA tier-1","role":"reference"}'
   ```
2. For collection types (keyframe, sfx, ref_image), use `--label`:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload <shotUUID> sfx /path/to/city_ambience.mp3 --label "City ambience"
   ```
3. For user-uploaded assets (no generation info), use `--method user_upload --user-note`:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload <shotUUID> ref_image /path/to/ref.png \
     --label "Character ref" --method user_upload --user-note "From LoRA training set"
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
Then review insights (see "Before Writing or Updating Prompts" below), fix the prompt, and re-roll. **Never re-roll without changing something.**

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

### Asset Provenance

Every asset should record how it was made. Provenance is **always optional** — it never blocks uploads.

**Record inline during upload** (preferred — one API call):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py upload <shotUUID> end_frame /path/to/end.png \
  --method ai_generated --model "gpt-image-2" \
  --prompt "Based on start_frame, generate end frame of 5s slow push-in..." \
  --parent '{"assetId":"<start-frame-id>","role":"base"}'
```

**Record after the fact** (for existing assets missing provenance):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py set-provenance <assetId> \
  --method user_upload --user-note "Downloaded from Midjourney, prompt: ..."
```

**Query provenance and lineage**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py provenance <assetId>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py lineage <assetId> --depth 3
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nl.py roll-snapshot <rollId>
```

#### Methods
- `ai_generated` — created by an AI model (record model + prompt)
- `user_upload` — manually uploaded by user (record user_note)
- `manual_edit` — edited by hand from an existing asset
- `derived` — mechanically transformed (e.g. padded audio from dialogue)

#### Parent roles
- `base` — primary input the asset was derived from
- `reference` — visual reference that guided generation
- `style` — style reference
- `mask` — mask or segmentation input
- `composition` — layout/composition reference
- `audio` — audio input (for audio-driven generation)

#### When to record provenance
- **Always** when you generate an asset with an AI model — this is the most valuable lineage data.
- **Best-effort** for user uploads — at minimum record `method: user_upload`.
- **Skip** for trivial derivations that don't add information.
- `roll-snapshot` is recorded automatically when uploading a roll — no action needed.
