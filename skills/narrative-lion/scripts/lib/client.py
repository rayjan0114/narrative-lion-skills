"""Narrative Lion API client — stdlib only (urllib + json)."""

from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.request
import urllib.error
from typing import Generator

BASE_URL = "https://narrativelion.com"
USER_AGENT = "NarrativeLion-CLI/1.0"


def get_api_key() -> str:
    key = os.environ.get("NLK_API_KEY", "")
    if not key:
        print("Error: NLK_API_KEY not set. Export it first:", file=sys.stderr)
        print("  export NLK_API_KEY=nlk_xxxxxxxx", file=sys.stderr)
        sys.exit(1)
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def graphql(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query/mutation. Returns the full response dict."""
    body = {"query": query}
    if variables:
        body["variables"] = variables

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/graphql",
        data=data,
        headers=_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.readable() else ""
        print(f"Error: HTTP {e.code} from GraphQL", file=sys.stderr)
        if body_text:
            try:
                err = json.loads(body_text)
                for gql_err in err.get("errors", []):
                    print(f"  {gql_err.get('message', '')}", file=sys.stderr)
            except json.JSONDecodeError:
                print(f"  {body_text[:500]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)

    if "errors" in result and result["errors"]:
        for err in result["errors"]:
            code = err.get("extensions", {}).get("code", "")
            msg = err.get("message", "Unknown error")
            prefix = f"[{code}] " if code else ""
            print(f"Error: {prefix}{msg}", file=sys.stderr)
        sys.exit(1)

    return result.get("data", {})


def rest_get(path: str) -> dict:
    """GET a REST endpoint. Returns parsed JSON."""
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers=_headers(),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} from {path}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)


def rest_post(path: str, body: dict) -> dict:
    """POST to a REST endpoint. Returns parsed JSON."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.readable() else ""
        print(f"Error: HTTP {e.code} from {path}", file=sys.stderr)
        if body_text:
            print(f"  {body_text[:500]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)


def upload_binary(url: str, file_path: str, content_type: str = "application/octet-stream") -> None:
    """PUT binary data to a URL (asset/roll upload)."""
    with open(file_path, "rb") as f:
        data = f.read()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": content_type,
            "User-Agent": USER_AGENT,
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} uploading to {url}", file=sys.stderr)
        sys.exit(1)


def download_binary(url: str, output_path: str) -> None:
    """GET binary data from a URL and save to a local file."""
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} downloading {url}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)


def new_uuid() -> str:
    return str(uuid.uuid4())


def set_active_note(thread_id: str, note_id: str) -> None:
    """POST /api/threads/:threadId/active-note."""
    data = json.dumps({"noteId": note_id}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/threads/{thread_id}/active-note",
        data=data,
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.readable() else ""
        print(f"Error: HTTP {e.code} setting active note", file=sys.stderr)
        if body_text:
            print(f"  {body_text[:500]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)


def stream_sse(path: str, body: dict) -> Generator[dict, None, None]:
    """POST to an SSE endpoint. Yields parsed event dicts."""
    data = json.dumps(body).encode()
    headers = _headers()
    headers["Accept"] = "text/event-stream"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.readable() else ""
        print(f"Error: HTTP {e.code} from {path}", file=sys.stderr)
        if body_text:
            try:
                err = json.loads(body_text)
                msg = err.get("error", err.get("message", body_text[:200]))
                code = err.get("code", "")
                prefix = f"[{code}] " if code else ""
                print(f"  {prefix}{msg}", file=sys.stderr)
            except json.JSONDecodeError:
                print(f"  {body_text[:500]}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: Network error — {e.reason}", file=sys.stderr)
        sys.exit(1)

    try:
        buffer = ""
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            if line.startswith("data: "):
                buffer = line[6:]
            elif line == "" and buffer:
                try:
                    yield json.loads(buffer)
                except json.JSONDecodeError:
                    pass
                buffer = ""
    finally:
        resp.close()
