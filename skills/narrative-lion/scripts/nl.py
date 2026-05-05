#!/usr/bin/env python3
"""Narrative Lion CLI — wraps the NL GraphQL/REST API for agent and human use."""

import sys
import os

# Add scripts/ to path so lib/ and commands/ are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from commands import search, notes, billing, export, filmwork, chat

HELP = """\
Usage: nl.py <command> [args...] [--json]

General:
  search <query> [--collection ID]        Semantic search
  fts <query> [--collection ID]           Full-text search
  notes list [--collection ID] [--type T] Browse notes
  notes get <noteId>                      Get note details
  notes create --type T --content C       Create note
  export <noteId> [noteId2 ...]           Export notes as zip
  usage                                   Credit usage

Film Director:
  director <concept> [--type T] [--duration N] [--aspect R] [--style S] [--thread ID]
      Generate storyboard from concept. (LLM cost: 1-2 credits)
  director-persist <threadId> --storyboard <md> --instruction <text> [--immediate]
      Persist storyboard as filmwork note. (no LLM cost)

Filmwork:
  overview <noteId>                       Project overview
  shot <noteId> <label>                   Shot detail + preflight + assets + rolls
  preflight <noteId> <label>              Preflight check only
  upload <shotId> <type> <file> [--label] Upload asset (3-step)
  upload-roll <shotId> <file> [--seed N --model M --prompt-version N]
  shot-update <shotId> [--status S] [--prompts JSON] [--dialogue JSON] [--direction JSON] [--model-config JSON] [--duration N]
                                          Update shot status / fields
  score <rollId> --face N --expr N --motion N --stability N --style N
  verdict <rollId> <approved|rejected>    Set roll verdict
  golden-roll <rollId>                    Set golden roll
  decision <noteId> [--shot ID] --action A --reason R --outcome O
  insight <noteId> --category C --title T --detail D
  decisions <noteId> [--shot ID]          List decisions
  insights <noteId> [--category C]        List insights

Download:
  download <assetId> <output_path>        Download a single asset
  download-shot <noteId> <label> [--dir D] [--all]
      Download golden assets for a shot (or --all versions)

Provenance:
  provenance <assetId>                    Query asset provenance
  lineage <assetId> [--depth N]           Query lineage DAG edges
  roll-snapshot <rollId>                  What assets were used to generate a roll
  set-provenance <assetId> --method M [--model M] [--prompt P] [--parent JSON ...]

Flags:
  --json    Output raw JSON (for piping)
"""

COMMANDS = {
    "search": search.search,
    "fts": search.fts,
    "usage": billing.usage,
    "export": export.export_notes,
    "director": chat.director,
    "director-persist": chat.director_persist,
    "overview": filmwork.overview,
    "shot": filmwork.shot,
    "preflight": filmwork.preflight,
    "upload": filmwork.upload_asset,
    "upload-roll": filmwork.upload_roll,
    "shot-update": filmwork.shot_update,
    "score": filmwork.score,
    "verdict": filmwork.verdict,
    "golden-roll": filmwork.golden_roll,
    "decision": filmwork.add_decision,
    "insight": filmwork.add_insight,
    "decisions": filmwork.list_decisions,
    "insights": filmwork.list_insights,
    "provenance": filmwork.provenance,
    "lineage": filmwork.lineage,
    "roll-snapshot": filmwork.roll_snapshot,
    "set-provenance": filmwork.set_provenance,
    "download": filmwork.download_asset,
    "download-shot": filmwork.download_shot,
}

NOTES_SUBCOMMANDS = {
    "list": notes.list_notes,
    "get": notes.get_note,
    "create": notes.create_note,
}


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP)
        return

    json_mode = "--json" in args
    if json_mode:
        args = [a for a in args if a != "--json"]

    cmd = args[0]
    rest = args[1:]

    if cmd == "notes":
        subcmd = rest[0] if rest else "list"
        sub_rest = rest[1:] if rest else []
        handler = NOTES_SUBCOMMANDS.get(subcmd)
        if not handler:
            print(f"Unknown notes subcommand: {subcmd}")
            print(f"Available: {', '.join(NOTES_SUBCOMMANDS.keys())}")
            return
        handler(sub_rest, json_mode=json_mode)
    elif cmd in COMMANDS:
        COMMANDS[cmd](rest, json_mode=json_mode)
    else:
        print(f"Unknown command: {cmd}")
        print(f"Run 'nl.py --help' for usage.")


if __name__ == "__main__":
    main()
