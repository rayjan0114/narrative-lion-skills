"""Export command."""

from __future__ import annotations

from lib.client import rest_post
from lib.formatters import as_json


def export_notes(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py export <noteId> [noteId2 ...]")
        return

    note_ids = [a for a in args if not a.startswith("--")]
    data = rest_post("/api/export/request", {"noteIds": note_ids})

    if json_mode:
        print(as_json(data))
        return

    url = data.get("url") or data.get("downloadUrl") or ""
    if url:
        print(f"  Download: {url}")
        print("  Tip: Use bsdtar to extract (handles non-ASCII filenames):")
        print("    bsdtar -xf notes.zip -C notes/")
    else:
        print("  Export requested. Check response for download details.")
        print(as_json(data))
