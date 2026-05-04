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

## Filmwork (AI Video Shot Production)

The skill includes full support for Narrative Lion's Filmwork pipeline:

- **Film Director**: AI-guided storyboard generation from a concept
- **Direct creation**: Zero-credit path for pre-written storyboards
- **Shot editing**: Modify direction, prompts, dialogue via natural language
- **Refinement**: AI suggestions and streaming storyboard revisions

See the [full docs](https://narrativelion.com/docs#filmwork-pipeline) for details.

## Skill Authoring Guidelines

- Skill files should focus on **best practices** and **high-level architecture** — gotchas, common mistakes, decision points.
- Keep everything else minimal. Full schema details (field names, argument types, payloads) belong in the [API docs](https://narrativelion.com/docs), not in skill files.
- Include just enough operation signatures for the agent to make API calls without fetching the docs for common tasks.
- **MUST WebFetch docs** is intentional: because the skill only covers best practices and high-level architecture, the agent needs to fetch the full API docs (`/docs`, `/docs/filmwork`, etc.) at least once per conversation to get exact field names, argument types, and payloads before making API calls.

## Reference

Full API docs: https://narrativelion.com/docs

## License

MIT
