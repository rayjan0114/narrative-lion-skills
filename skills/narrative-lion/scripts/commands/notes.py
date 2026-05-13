"""Notes commands: list, get, create."""

from __future__ import annotations

from lib.client import graphql
from lib.formatters import as_json, table


def list_notes(args: list[str], json_mode: bool = False) -> None:
    collection_id = None
    uncategorized = False
    note_type = None
    starred = None
    sort = None
    limit = None
    offset = None
    tags = None

    i = 0
    while i < len(args):
        if args[i] == "--collection" and i + 1 < len(args):
            collection_id = args[i + 1]; i += 2
        elif args[i] == "--uncategorized":
            uncategorized = True; i += 1
        elif args[i] == "--type" and i + 1 < len(args):
            note_type = args[i + 1]; i += 2
        elif args[i] == "--starred":
            starred = True; i += 1
        elif args[i] == "--sort" and i + 1 < len(args):
            sort = args[i + 1]; i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1]); i += 2
        elif args[i] == "--offset" and i + 1 < len(args):
            offset = int(args[i + 1]); i += 2
        elif args[i] == "--tags" and i + 1 < len(args):
            tags = [t.strip() for t in args[i + 1].split(",")]; i += 2
        else:
            i += 1

    gql = """
    query($noteType: String, $starred: Boolean, $collectionId: String,
          $uncategorized: Boolean, $sort: String, $limit: Int, $offset: Int, $tags: [String!]) {
      browseNotes(noteType: $noteType, starred: $starred, collectionId: $collectionId,
                  uncategorized: $uncategorized, sort: $sort, limit: $limit, offset: $offset, tags: $tags) {
        id title noteType createdAt updatedAt starredAt tags
      }
    }"""
    variables: dict = {}
    if collection_id:
        variables["collectionId"] = collection_id
    if uncategorized:
        variables["uncategorized"] = True
    if note_type:
        variables["noteType"] = note_type
    if starred:
        variables["starred"] = True
    if sort:
        variables["sort"] = sort
    if limit is not None:
        variables["limit"] = limit
    if offset is not None:
        variables["offset"] = offset
    if tags:
        variables["tags"] = tags

    data = graphql(gql, variables)
    notes = data.get("browseNotes", [])

    if json_mode:
        print(as_json(notes))
        return

    if not notes:
        print("No notes found.")
        return

    for n in notes:
        note_id = n.get("id", "")
        title = n.get("title") or "(untitled)"
        ntype = n.get("noteType") or ""
        date = (n.get("updatedAt") or "")[:10]
        star = "*" if n.get("starredAt") else " "
        print(f"  {star} {date}  {ntype:<9}  {note_id}  {title[:60]}")


def get_note(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py notes get <noteId>")
        return

    note_id = args[0]
    gql = """
    query($noteId: String!) {
      note(noteId: $noteId) {
        id videoId noteType lang title noteMd metadata tags collections { id name }
        starredAt createdAt updatedAt
      }
    }"""

    data = graphql(gql, {"noteId": note_id})
    note = data.get("note")

    if json_mode:
        print(as_json(note))
        return

    if not note:
        print(f"Note {note_id} not found.")
        return

    title = note.get("title") or "(untitled)"
    note_type = note.get("noteType") or "general"
    print(f"  Title:   {title}")
    print(f"  Type:    {note_type}")
    print(f"  ID:      {note.get('id')}")
    print(f"  Tags:    {', '.join(note.get('tags') or []) or '(none)'}")
    print(f"  Updated: {note.get('updatedAt', '')}")
    md = note.get("noteMd") or ""
    if md:
        preview = "\n".join(md.split("\n")[:10])
        print(f"\n{preview}")
        if len(md.split("\n")) > 10:
            print(f"\n  ... ({len(md)} chars total)")


def create_note(args: list[str], json_mode: bool = False) -> None:
    note_type = "general"
    content = ""
    skip_ai = False

    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            note_type = args[i + 1]; i += 2
        elif args[i] == "--content" and i + 1 < len(args):
            content = args[i + 1]; i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                content = f.read()
            i += 2
        elif args[i] == "--skip-ai":
            skip_ai = True; i += 1
        else:
            i += 1

    if not content:
        print("Usage: nl.py notes create --type <type> --content <text> [--file path] [--skip-ai]")
        return

    gql = """
    mutation($content: String!, $noteType: String, $skipAi: Boolean) {
      createGeneralNote(content: $content, noteType: $noteType, skipAi: $skipAi) {
        id noteMd createdAt
      }
    }"""
    variables: dict = {"content": content, "noteType": note_type}
    if skip_ai:
        variables["skipAi"] = True

    data = graphql(gql, variables)
    note = data.get("createGeneralNote")

    if json_mode:
        print(as_json(note))
        return

    print(f"  Created: {note.get('id')}")
    print(f"  Type:    {note_type}")


def update_note(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py notes update <noteId> [--content <text>] [--metadata <json>] [--file <path>]")
        return

    note_id = args[0]
    content = None
    metadata = None

    i = 1
    while i < len(args):
        if args[i] == "--content" and i + 1 < len(args):
            content = args[i + 1]; i += 2
        elif args[i] == "--metadata" and i + 1 < len(args):
            metadata = args[i + 1]; i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            with open(args[i + 1]) as f:
                file_content = f.read()
            if file_content.lstrip().startswith("{"):
                metadata = file_content
            else:
                content = file_content
            i += 2
        else:
            i += 1

    if content is None and metadata is None:
        print("Provide --content, --metadata, or --file")
        return

    gql = """
    mutation($noteId: String!, $noteMd: String, $metadata: String) {
      updateNote(noteId: $noteId, noteMd: $noteMd, metadata: $metadata) {
        id noteMd metadata updatedAt
      }
    }"""
    variables: dict = {"noteId": note_id}
    if content is not None:
        variables["noteMd"] = content
    if metadata is not None:
        variables["metadata"] = metadata

    data = graphql(gql, variables)
    note = data.get("updateNote")

    if json_mode:
        print(as_json(note))
        return

    print(f"  Updated: {note.get('id')}")
    print(f"  At:      {note.get('updatedAt')}")
