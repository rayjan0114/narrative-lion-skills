# Narrative Lion Skills

AI agent skills for working with [Narrative Lion](https://narrativelion.com) — generate notes from YouTube, search your knowledge base, chat with your notes, produce AI video shot pipelines, and export, all via the Narrative Lion API.

## Install

Works with Claude Code, Cursor, Codex CLI, OpenCode, and 40+ other AI tools.

```bash
npx skills add rayjan0114/narrative-lion-skills
```

## Setup

1. Create an API key at [narrativelion.com/settings/api-keys](https://narrativelion.com/settings/api-keys) (Pro plan required).
2. Export it in your shell:

   ```bash
   export NLK_API_KEY=nlk_xxxxxxxx
   ```

## Usage

After install, your AI agent has access to the `narrative-lion` skill. Just ask:

- "Generate a Narrative Lion note from this YouTube URL: ..."
- "Search my Narrative Lion notes for X"
- "Create a filmwork project from this storyboard"
- "Edit shot 01A to change the camera angle"
- "Export all my notes as Markdown"

## Architecture

The skill uses a **CLI-first** approach following [Anthropic's skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

```
skills/narrative-lion/
├── SKILL.md                    # Decision guidance + command reference
└── scripts/
    ├── nl.py                   # CLI entry point
    ├── lib/
    │   ├── client.py           # GraphQL/REST client, auth, error handling
    │   └── formatters.py       # Output formatting
    └── commands/
        ├── search.py           # search, fts
        ├── notes.py            # notes list/get/create
        ├── filmwork.py         # overview, shot, upload, score, verdict, ...
        ├── export.py           # export
        └── billing.py          # usage
```

- **SKILL.md** = high-freedom decisions (what to do, when, why)
- **scripts/** = low-freedom operations (exact API calls, zero guessing)

This is ~35x more token-efficient than MCP and eliminates GraphQL field-name errors.

## Filmwork (AI Video Shot Production)

The skill includes full support for Narrative Lion's Filmwork pipeline:

- **Film Director**: AI-guided storyboard generation from a concept
- **Direct creation**: Zero-credit path for pre-written storyboards
- **Shot editing**: Modify direction, prompts, dialogue, model config via `shot-update`
- **Refinement**: AI suggestions and streaming storyboard revisions
- **Provenance**: Track how every asset was made, with full lineage DAG

See the [full docs](https://narrativelion.com/docs#filmwork-pipeline) for details.

## Skill Authoring Guidelines

- **SKILL.md** focuses on best practices, decision guidance, and command reference.
- **scripts/** handles all API interactions — agents call CLI commands via Bash, not raw GraphQL.
- Scripts use stdlib only (no pip install required).
- For operations not covered by the CLI (e.g. SSE chat), agents may use curl directly — refer to the full [API docs](https://narrativelion.com/docs).

## Reference

Full API docs: https://narrativelion.com/docs

## License

MIT
