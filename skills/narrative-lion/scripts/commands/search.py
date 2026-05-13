"""Search commands: search, fts."""

from __future__ import annotations

import sys

from lib.client import graphql
from lib.formatters import as_json, table


def search(args: list[str], json_mode: bool = False) -> None:
    query_text = args[0] if args else ""
    if not query_text:
        print("Usage: nl.py search <query> [--collection ID]", file=sys.stderr)
        return

    collection_id = None
    if "--collection" in args:
        idx = args.index("--collection")
        collection_id = args[idx + 1] if idx + 1 < len(args) else None

    gql = """
    query($query: String!, $collectionId: String) {
      search(query: $query, collectionId: $collectionId) {
        id videoId title noteMd score
      }
    }"""
    variables: dict = {"query": query_text}
    if collection_id:
        variables["collectionId"] = collection_id

    data = graphql(gql, variables)
    results = data.get("search", [])

    if json_mode:
        print(as_json(results))
        return

    if not results:
        print("No results found.")
        return

    for r in results:
        title = (r.get("title") or "(untitled)")[:60]
        score = r.get("score", "")
        note_id = r.get("id", "")
        print(f"  {note_id}  {title}  (score: {score})")


def fts(args: list[str], json_mode: bool = False) -> None:
    query_text = args[0] if args else ""
    if not query_text:
        print("Usage: nl.py fts <query> [--collection ID]", file=sys.stderr)
        return

    collection_id = None
    if "--collection" in args:
        idx = args.index("--collection")
        collection_id = args[idx + 1] if idx + 1 < len(args) else None

    gql = """
    query($query: String!, $collectionId: String) {
      ftsSearch(query: $query, collectionId: $collectionId) {
        id videoId noteType snippet rank
      }
    }"""
    variables: dict = {"query": query_text}
    if collection_id:
        variables["collectionId"] = collection_id

    data = graphql(gql, variables)
    results = data.get("ftsSearch", [])

    if json_mode:
        print(as_json(results))
        return

    if not results:
        print("No results found.")
        return

    for r in results:
        snippet = (r.get("snippet") or "")[:80]
        note_id = r.get("id", "")
        print(f"  {note_id}  {snippet}")
