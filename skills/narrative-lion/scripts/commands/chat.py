"""Chat/SSE commands: chat, filmwork-edit, director, director-persist, director-refine, director-suggestions."""

from __future__ import annotations

import json
import sys

from lib.client import stream_sse, set_active_note, rest_post, new_uuid
from lib.formatters import as_json


# ---------------------------------------------------------------------------
# SSE event handler (shared)
# ---------------------------------------------------------------------------

def _handle_stream(path: str, body: dict, json_mode: bool, thread_id: str) -> dict | None:
    """Stream SSE events, print tokens, return the complete event."""
    collected_text = ""
    final: dict | None = None

    for event in stream_sse(path, body):
        et = event.get("eventType", "")

        if et == "token":
            content = event.get("content", "")
            if not json_mode:
                print(content, end="", flush=True)
            collected_text += content

        elif et == "state":
            pass

        elif et == "error":
            code = event.get("code", "")
            msg = event.get("message", "Unknown error")
            prefix = f"[{code}] " if code else ""
            print(f"\nError: {prefix}{msg}", file=sys.stderr)
            sys.exit(1)

        elif et == "complete":
            final = event
            if not json_mode:
                print()

    if json_mode:
        result: dict = {"threadId": thread_id}
        if final:
            result["finalMessage"] = final.get("finalMessage", collected_text)
            artifacts = final.get("artifacts", {})
            if artifacts:
                result["artifacts"] = artifacts
        else:
            result["finalMessage"] = collected_text
        print(as_json(result))

    return final


def _build_chat_body(thread_id: str, text: str, extra_payload: dict | None = None) -> dict:
    payload: dict = {"text": text}
    if extra_payload:
        payload.update(extra_payload)
    return {
        "threadId": thread_id,
        "actionId": new_uuid(),
        "event": {
            "type": "user_text",
            "payload": payload,
        },
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def chat(args: list[str], json_mode: bool = False) -> None:
    """General chat — Q&A about notes."""
    text = ""
    thread_id = None
    note_id = None

    i = 0
    positional_done = False
    while i < len(args):
        if args[i] == "--thread" and i + 1 < len(args):
            thread_id = args[i + 1]; i += 2
        elif args[i] == "--note" and i + 1 < len(args):
            note_id = args[i + 1]; i += 2
        elif not positional_done and not args[i].startswith("--"):
            text = args[i]; positional_done = True; i += 1
        else:
            i += 1

    if not text:
        print("Usage: nl.py chat <text> [--thread ID] [--note noteId]"); return

    thread_id = thread_id or new_uuid()

    if note_id:
        set_active_note(thread_id, note_id)

    body = _build_chat_body(thread_id, text)
    final = _handle_stream("/api/chat/stream", body, json_mode, thread_id)

    if not json_mode:
        print(f"\n  threadId: {thread_id}")


def filmwork_edit(args: list[str], json_mode: bool = False) -> None:
    """Edit filmwork shots via natural language."""
    note_id = None
    text = ""
    thread_id = None

    i = 0
    positionals: list[str] = []
    while i < len(args):
        if args[i] == "--thread" and i + 1 < len(args):
            thread_id = args[i + 1]; i += 2
        elif not args[i].startswith("--"):
            positionals.append(args[i]); i += 1
        else:
            i += 1

    if len(positionals) < 2:
        print("Usage: nl.py filmwork-edit <noteId> <instruction> [--thread ID]"); return

    note_id = positionals[0]
    text = positionals[1]
    thread_id = thread_id or new_uuid()

    set_active_note(thread_id, note_id)

    body = _build_chat_body(thread_id, text)
    final = _handle_stream("/api/chat/stream", body, json_mode, thread_id)

    if not json_mode:
        if final:
            fw = final.get("artifacts", {}).get("filmworkUpdate")
            if fw:
                print(f"\n  Filmwork update: {fw.get('summary', '')}")
                for ch in fw.get("changes", []):
                    print(f"    [{ch.get('shotLabel', '?')}] modified")
        print(f"\n  threadId: {thread_id}")


def director(args: list[str], json_mode: bool = False) -> None:
    """Film Director — generate storyboard from concept."""
    text = ""
    thread_id = None
    video_type = "animate"
    duration = 30
    aspect = "16:9"
    visual_style = None

    i = 0
    positional_done = False
    while i < len(args):
        if args[i] == "--thread" and i + 1 < len(args):
            thread_id = args[i + 1]; i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            video_type = args[i + 1]; i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = int(args[i + 1]); i += 2
        elif args[i] == "--aspect" and i + 1 < len(args):
            aspect = args[i + 1]; i += 2
        elif args[i] == "--style" and i + 1 < len(args):
            visual_style = args[i + 1]; i += 2
        elif not positional_done and not args[i].startswith("--"):
            text = args[i]; positional_done = True; i += 1
        else:
            i += 1

    if not text:
        print("Usage: nl.py director <concept> [--type animate|short|cinematic] [--duration N] [--aspect 16:9] [--style S] [--thread ID]"); return

    thread_id = thread_id or new_uuid()

    extra: dict = {
        "activeTool": "film_director",
        "filmDirectorVideoType": video_type,
        "filmDirectorTargetDurationSec": duration,
        "filmDirectorAspectRatio": aspect,
    }
    if visual_style:
        extra["filmDirectorVisualStyle"] = visual_style

    body = _build_chat_body(thread_id, text, extra)
    _handle_stream("/api/chat/stream", body, json_mode, thread_id)

    if not json_mode:
        print(f"\n  threadId: {thread_id}")
        print(f"  To persist: nl.py director-persist {thread_id} ...")


def director_persist(args: list[str], json_mode: bool = False) -> None:
    """Persist storyboard as filmwork note."""
    thread_id = None
    storyboard = ""
    video_type = "animate"
    duration = 30
    aspect = "16:9"
    instruction = ""
    visual_style = None
    immediate = False

    i = 0
    positionals: list[str] = []
    while i < len(args):
        if args[i] == "--storyboard" and i + 1 < len(args):
            storyboard = args[i + 1]; i += 2
        elif args[i] == "--storyboard-file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                storyboard = f.read()
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            video_type = args[i + 1]; i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = int(args[i + 1]); i += 2
        elif args[i] == "--aspect" and i + 1 < len(args):
            aspect = args[i + 1]; i += 2
        elif args[i] == "--instruction" and i + 1 < len(args):
            instruction = args[i + 1]; i += 2
        elif args[i] == "--style" and i + 1 < len(args):
            visual_style = args[i + 1]; i += 2
        elif args[i] == "--immediate":
            immediate = True; i += 1
        elif not args[i].startswith("--"):
            positionals.append(args[i]); i += 1
        else:
            i += 1

    if not positionals:
        print("Usage: nl.py director-persist <threadId> --storyboard <md> --instruction <text> [--type T] [--duration N] [--aspect R] [--immediate]"); return

    thread_id = positionals[0]

    if not storyboard or not instruction:
        print("Error: --storyboard (or --storyboard-file) and --instruction are required", file=sys.stderr); return

    body: dict = {
        "threadId": thread_id,
        "storyboard": storyboard,
        "setup": {
            "videoType": video_type,
            "targetDurationSec": duration,
            "aspectRatio": aspect,
            "instruction": instruction,
        },
    }
    if visual_style:
        body["setup"]["visualStyle"] = visual_style
    if immediate:
        body["immediate"] = True

    data = rest_post("/api/filmwork/director/persist", body)

    if json_mode:
        print(as_json(data)); return

    print(f"  Persisted: noteId={data.get('noteId')}, shots={data.get('shotCount')}")


def director_refine(args: list[str], json_mode: bool = False) -> None:
    """Refine storyboard (SSE stream of revised markdown)."""
    storyboard = ""
    video_type = "animate"
    duration = 30
    aspect = "16:9"
    instruction = ""
    prompt = ""

    i = 0
    while i < len(args):
        if args[i] == "--storyboard" and i + 1 < len(args):
            storyboard = args[i + 1]; i += 2
        elif args[i] == "--storyboard-file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                storyboard = f.read()
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            video_type = args[i + 1]; i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = int(args[i + 1]); i += 2
        elif args[i] == "--aspect" and i + 1 < len(args):
            aspect = args[i + 1]; i += 2
        elif args[i] == "--instruction" and i + 1 < len(args):
            instruction = args[i + 1]; i += 2
        elif args[i] == "--prompt" and i + 1 < len(args):
            prompt = args[i + 1]; i += 2
        else:
            i += 1

    if not storyboard or not instruction or not prompt:
        print("Usage: nl.py director-refine --storyboard <md> --instruction <text> --prompt <refinement>"); return

    body = {
        "currentStoryboard": storyboard,
        "setup": {
            "videoType": video_type,
            "targetDurationSec": duration,
            "aspectRatio": aspect,
            "instruction": instruction,
        },
        "refinementPrompt": prompt,
    }

    collected = ""
    for event in stream_sse("/api/filmwork/director/refine", body):
        et = event.get("eventType", "")
        if et == "token":
            content = event.get("content", event.get("t", ""))
            if not json_mode:
                print(content, end="", flush=True)
            collected += content
        elif et == "error":
            print(f"\nError: {event.get('message', '')}", file=sys.stderr)
            sys.exit(1)

    if json_mode:
        print(as_json({"storyboard": collected}))
    else:
        print()


def director_suggestions(args: list[str], json_mode: bool = False) -> None:
    """Get AI suggestions for storyboard refinement."""
    storyboard = ""
    video_type = "animate"
    duration = 30
    aspect = "16:9"
    instruction = ""

    i = 0
    while i < len(args):
        if args[i] == "--storyboard" and i + 1 < len(args):
            storyboard = args[i + 1]; i += 2
        elif args[i] == "--storyboard-file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                storyboard = f.read()
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            video_type = args[i + 1]; i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = int(args[i + 1]); i += 2
        elif args[i] == "--aspect" and i + 1 < len(args):
            aspect = args[i + 1]; i += 2
        elif args[i] == "--instruction" and i + 1 < len(args):
            instruction = args[i + 1]; i += 2
        else:
            i += 1

    if not storyboard or not instruction:
        print("Usage: nl.py director-suggestions --storyboard <md> --instruction <text>"); return

    body = {
        "storyboard": storyboard,
        "setup": {
            "videoType": video_type,
            "targetDurationSec": duration,
            "aspectRatio": aspect,
            "instruction": instruction,
        },
    }

    data = rest_post("/api/filmwork/director/refine-suggestions", body)

    if json_mode:
        print(as_json(data)); return

    suggestions = data.get("suggestions", [])
    if not suggestions:
        print("  No suggestions."); return

    for s in suggestions:
        print(f"  [{s.get('label', '?')}] {s.get('prompt', '')}")
