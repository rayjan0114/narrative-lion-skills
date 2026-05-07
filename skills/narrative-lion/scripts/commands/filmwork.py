"""Filmwork commands: overview, shot, preflight, upload, score, verdict, etc."""

from __future__ import annotations

import json
import mimetypes
import os
import sys

from lib.client import graphql, upload_binary, download_binary, BASE_URL
from lib.formatters import as_json, status_bar


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def overview(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py overview <noteId>"); return
    note_id = args[0]

    gql = """
    query($noteId: String!) {
      filmworkOverview(noteId: $noteId) {
        noteId title totalShots
        statusCounts { notStarted assetPrep ready generating review done blocked }
        shots {
          shotId status
          assetCounts { startFrame endFrame keyframe dialogue sfx paddedAudio refVideo refImage total }
          rollSummary { total pending approved rejected bestScore goldenRollId }
          preflightStatus { ready }
        }
        linkedNotes { id targetNoteId targetNoteTitle linkType }
      }
    }"""
    data = graphql(gql, {"noteId": note_id})
    ov = data.get("filmworkOverview")
    if not ov:
        print(f"Filmwork not found: {note_id}"); return

    if json_mode:
        print(as_json(ov)); return

    counts = ov.get("statusCounts", {})
    total = ov.get("totalShots", 0)
    print(f"{ov.get('title', '')}")
    print(f"  {status_bar(counts, total)}")
    print()

    shots = ov.get("shots", [])
    print(f"  {'Shot':<6} {'Status':<12} {'Assets':<8} {'Rolls':<8} {'Best':<6} {'PF'}")
    print(f"  {'----':<6} {'------':<12} {'------':<8} {'-----':<8} {'----':<6} {'--'}")
    for s in shots:
        label = s.get("shotId", "?")
        status = s.get("status", "?")
        ac = s.get("assetCounts", {})
        rs = s.get("rollSummary", {})
        pf = s.get("preflightStatus", {})
        asset_total = ac.get("total", 0)
        roll_total = rs.get("total", 0)
        best = rs.get("bestScore") or "-"
        ready = "Y" if pf.get("ready") else "N"
        print(f"  {label:<6} {status:<12} {asset_total:<8} {roll_total:<8} {best:<6} {ready}")

    links = ov.get("linkedNotes", [])
    if links:
        print(f"\n  Linked Notes:")
        for ln in links:
            print(f"    [{ln.get('linkType','')}] {ln.get('targetNoteTitle','?')} ({ln.get('targetNoteId','')})")


def shot(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py shot <noteId> <label>"); return
    note_id, label = args[0], args[1]

    gql = """
    query($noteId: String!, $shotLabel: String!) {
      filmworkShotByLabel(noteId: $noteId, shotLabel: $shotLabel) {
        id shotId status targetDurationSec dialogue
        directionJson promptsJson modelConfigJson blockerJson
        preflightStatus { ready checks { name passed detail } }
        assetCounts { startFrame endFrame keyframe dialogue sfx paddedAudio refVideo refImage total }
        rollSummary { total pending approved rejected bestScore goldenRollId }
        assets { id assetType label url version isGolden agentHold }
        rolls { id rollNumber seed modelUsed promptVersion totalScore verdict isGolden agentHold }
      }
    }"""
    data = graphql(gql, {"noteId": note_id, "shotLabel": label})
    s = data.get("filmworkShotByLabel")
    if not s:
        print(f"Shot {label} not found in {note_id}"); return

    if json_mode:
        print(as_json(s)); return

    print(f"Shot {s.get('shotId')} (UUID: {s.get('id')})")
    print(f"  Status:   {s.get('status')}")
    print(f"  Duration: {s.get('targetDurationSec', '?')}s")

    pf = s.get("preflightStatus", {})
    checks = pf.get("checks", [])
    ready = pf.get("ready", False)
    print(f"  Preflight: {'READY' if ready else 'NOT READY'}")
    for c in checks:
        mark = "+" if c.get("passed") else "x"
        detail = f" — {c['detail']}" if c.get("detail") else ""
        print(f"    [{mark}] {c.get('name','')}{detail}")

    blocker = s.get("blockerJson")
    if blocker:
        try:
            b = json.loads(blocker)
            print(f"  BLOCKER: {b.get('description', blocker)}")
        except (json.JSONDecodeError, TypeError):
            print(f"  BLOCKER: {blocker}")

    assets = s.get("assets", [])
    if assets:
        print(f"\n  Assets ({len(assets)}):")
        for a in assets:
            golden = " [GOLDEN]" if a.get("isGolden") else ""
            hold = " [HOLD]" if a.get("agentHold") else ""
            print(f"    {a.get('assetType'):<14} v{a.get('version',1)} {a.get('label') or ''}{golden}{hold}")
            print(f"      id: {a.get('id')}  url: {a.get('url','')[:80]}")

    rolls = s.get("rolls", [])
    if rolls:
        print(f"\n  Rolls ({len(rolls)}):")
        for r in rolls:
            golden = " [GOLDEN]" if r.get("isGolden") else ""
            hold = " [HOLD]" if r.get("agentHold") else ""
            score = r.get("totalScore") or "-"
            print(f"    #{r.get('rollNumber',0)}  {r.get('verdict','?'):<10} score={score}  model={r.get('modelUsed','?')}  seed={r.get('seed','?')}{golden}{hold}")
            print(f"      id: {r.get('id')}")

    prompts_raw = s.get("promptsJson")
    if prompts_raw:
        try:
            prompts = json.loads(prompts_raw)
            active = [p for p in prompts if p.get("isActive")]
            if active:
                print(f"\n  Active Prompt (v{active[0].get('version','?')}):")
                body = active[0].get("body", "")
                for line in body.split("\n")[:8]:
                    print(f"    {line}")
        except (json.JSONDecodeError, TypeError):
            pass


def preflight(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py preflight <noteId> <label>"); return
    note_id, label = args[0], args[1]

    gql = """
    query($noteId: String!, $shotLabel: String!) {
      filmworkShotByLabel(noteId: $noteId, shotLabel: $shotLabel) {
        id shotId
        preflightStatus { ready checks { name passed detail } }
      }
    }"""
    data = graphql(gql, {"noteId": note_id, "shotLabel": label})
    s = data.get("filmworkShotByLabel")
    if not s:
        print(f"Shot {label} not found"); return

    if json_mode:
        print(as_json(s.get("preflightStatus"))); return

    pf = s.get("preflightStatus", {})
    ready = pf.get("ready", False)
    print(f"Shot {s.get('shotId')}: {'READY' if ready else 'NOT READY'}")
    for c in pf.get("checks", []):
        mark = "+" if c.get("passed") else "x"
        detail = f" — {c['detail']}" if c.get("detail") else ""
        print(f"  [{mark}] {c.get('name','')}{detail}")


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def upload_asset(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 3:
        print("Usage: nl.py upload <shotId> <assetType> <file> [--label L]"); return

    shot_id = args[0]
    asset_type = args[1]
    file_path = args[2]

    label = None
    if "--label" in args:
        idx = args.index("--label")
        label = args[idx + 1] if idx + 1 < len(args) else None

    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr); return

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    # Step 1: Request upload URL
    gql_req = """
    mutation($shotId: String!, $assetType: String!, $filename: String!) {
      requestUploadUrl(shotId: $shotId, assetType: $assetType, filename: $filename) {
        uploadUrl assetKey
      }
    }"""
    data = graphql(gql_req, {"shotId": shot_id, "assetType": asset_type, "filename": filename})
    upload_info = data.get("requestUploadUrl", {})
    upload_url = upload_info.get("uploadUrl", "")
    asset_key = upload_info.get("assetKey", "")

    if not upload_url or not asset_key:
        print("Error: Failed to get upload URL", file=sys.stderr); return

    # Step 2: PUT binary
    print(f"  Uploading {filename}...")
    upload_binary(upload_url, file_path, content_type)

    # Parse optional provenance flags
    provenance_json = None
    prov_parts: dict = {}
    for flag, key in [("--method", "method"), ("--model", "model"), ("--prompt", "prompt"),
                      ("--user-note", "userNote"), ("--model-params", "modelParamsJson")]:
        if flag in args:
            idx = args.index(flag)
            if idx + 1 < len(args):
                prov_parts[key] = args[idx + 1]
    parent_flags = [i for i, a in enumerate(args) if a == "--parent"]
    if parent_flags:
        parents = []
        for idx in parent_flags:
            if idx + 1 < len(args):
                parents.append(json.loads(args[idx + 1]))
        prov_parts["parents"] = parents
    if "--provenance" in args:
        idx = args.index("--provenance")
        if idx + 1 < len(args):
            provenance_json = args[idx + 1]
    elif prov_parts.get("method"):
        provenance_json = json.dumps(prov_parts)

    # Step 3: Confirm
    gql_confirm = """
    mutation($shotId: String!, $assetKey: String!, $assetType: String!, $label: String, $provenanceJson: String) {
      confirmAssetUpload(shotId: $shotId, assetKey: $assetKey, assetType: $assetType, label: $label, provenanceJson: $provenanceJson) {
        id url status version isGolden
      }
    }"""
    confirm_vars: dict = {
        "shotId": shot_id,
        "assetKey": asset_key,
        "assetType": asset_type,
    }
    if label is not None:
        confirm_vars["label"] = label
    if provenance_json is not None:
        confirm_vars["provenanceJson"] = provenance_json

    data = graphql(gql_confirm, confirm_vars)
    asset = data.get("confirmAssetUpload", {})

    if json_mode:
        print(as_json(asset)); return

    golden = " [GOLDEN]" if asset.get("isGolden") else ""
    print(f"  Uploaded: {asset.get('id')}")
    print(f"  Version:  {asset.get('version')}{golden}")
    print(f"  URL:      {asset.get('url', '')[:100]}")


def upload_roll(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py upload-roll <shotId> <file> --seed N --model M --prompt-version N"); return

    shot_id = args[0]
    file_path = args[1]
    seed = None; model = None; prompt_version = None

    i = 2
    while i < len(args):
        if args[i] == "--seed" and i + 1 < len(args):
            seed = int(args[i + 1]); i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 2
        elif args[i] == "--prompt-version" and i + 1 < len(args):
            prompt_version = int(args[i + 1]); i += 2
        else:
            i += 1

    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr); return

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "video/mp4"

    # Step 1: Request upload URL
    gql_req = """
    mutation($shotId: String!, $filename: String!) {
      requestRollUploadUrl(shotId: $shotId, filename: $filename) {
        uploadUrl rollKey
      }
    }"""
    data = graphql(gql_req, {"shotId": shot_id, "filename": filename})
    info = data.get("requestRollUploadUrl", {})
    upload_url = info.get("uploadUrl", "")
    roll_key = info.get("rollKey", "")

    # Step 2: PUT binary
    print(f"  Uploading {filename}...")
    upload_binary(upload_url, file_path, content_type)

    # Step 3: Confirm
    gql_confirm = """
    mutation($shotId: String!, $rollKey: String!, $seed: Int, $modelUsed: String, $promptVersion: Int) {
      confirmRollUpload(shotId: $shotId, rollKey: $rollKey, seed: $seed, modelUsed: $modelUsed, promptVersion: $promptVersion) {
        id rollNumber url totalScore verdict
      }
    }"""
    confirm_vars: dict = {"shotId": shot_id, "rollKey": roll_key}
    if seed is not None:
        confirm_vars["seed"] = seed
    if model:
        confirm_vars["modelUsed"] = model
    if prompt_version is not None:
        confirm_vars["promptVersion"] = prompt_version

    data = graphql(gql_confirm, confirm_vars)
    roll = data.get("confirmRollUpload", {})

    if json_mode:
        print(as_json(roll)); return

    print(f"  Roll uploaded: {roll.get('id')}")
    print(f"  Roll #: {roll.get('rollNumber')}")


def score(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py score <rollId> --face N --expr N --motion N --stability N --style N"); return

    roll_id = args[0]
    scores: dict[str, int] = {}
    score_map = {
        "--face": "faceLikeness",
        "--expr": "expression",
        "--motion": "motionNatural",
        "--stability": "stability",
        "--style": "styleMatch",
    }

    i = 1
    while i < len(args):
        if args[i] in score_map and i + 1 < len(args):
            scores[score_map[args[i]]] = int(args[i + 1]); i += 2
        else:
            i += 1

    if len(scores) != 5:
        print("Error: All 5 dimensions required: --face --expr --motion --stability --style", file=sys.stderr)
        return

    # Compute weighted total
    weights = {"faceLikeness": 3, "expression": 3, "motionNatural": 2, "stability": 2, "styleMatch": 1}
    total = sum(scores[k] * weights[k] for k in scores)

    scorecard = json.dumps({"rubricVersion": 1, "scores": scores})

    gql = """
    mutation($rollId: String!, $scorecardJson: String!, $totalScore: Int!) {
      scoreRoll(rollId: $rollId, scorecardJson: $scorecardJson, totalScore: $totalScore) {
        id totalScore
      }
    }"""
    data = graphql(gql, {"rollId": roll_id, "scorecardJson": scorecard, "totalScore": total})
    result = data.get("scoreRoll", {})

    if json_mode:
        print(as_json(result)); return

    print(f"  Scored: {result.get('totalScore')}/55")
    for dim_id, val in scores.items():
        w = weights[dim_id]
        print(f"    {dim_id:<16} {val}/5 (x{w} = {val * w})")


def verdict(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py verdict <rollId> <approved|rejected>"); return

    roll_id = args[0]
    v = args[1]
    if v not in ("approved", "rejected"):
        print("Error: Verdict must be 'approved' or 'rejected'", file=sys.stderr); return

    gql = """
    mutation($rollId: String!, $verdict: String!) {
      updateRollVerdict(rollId: $rollId, verdict: $verdict) { id verdict }
    }"""
    data = graphql(gql, {"rollId": roll_id, "verdict": v})
    result = data.get("updateRollVerdict", {})

    if json_mode:
        print(as_json(result)); return
    print(f"  Roll {roll_id}: {result.get('verdict')}")


def golden_roll(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py golden-roll <rollId>"); return

    gql = """
    mutation($rollId: String!) {
      setGoldenRoll(rollId: $rollId) { id isGolden }
    }"""
    data = graphql(gql, {"rollId": args[0]})
    result = data.get("setGoldenRoll", {})

    if json_mode:
        print(as_json(result)); return
    print(f"  Roll {args[0]}: golden={result.get('isGolden')}")


def shot_update(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py shot-update <shotId> [--status S] [--blocker JSON] [--prompts JSON] [--dialogue JSON] [--direction JSON] [--model-config JSON] [--relations JSON] [--duration N]"); return

    shot_id = args[0]
    status = None; blocker = None
    prompts = None; dialogue = None; direction = None
    model_config = None; relations = None; duration = None

    i = 1
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]; i += 2
        elif args[i] == "--blocker" and i + 1 < len(args):
            blocker = args[i + 1]; i += 2
        elif args[i] == "--prompts" and i + 1 < len(args):
            prompts = args[i + 1]; i += 2
        elif args[i] == "--dialogue" and i + 1 < len(args):
            dialogue = args[i + 1]; i += 2
        elif args[i] == "--direction" and i + 1 < len(args):
            direction = args[i + 1]; i += 2
        elif args[i] == "--model-config" and i + 1 < len(args):
            model_config = args[i + 1]; i += 2
        elif args[i] == "--relations" and i + 1 < len(args):
            relations = args[i + 1]; i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = float(args[i + 1]); i += 2
        else:
            i += 1

    has_shot_fields = any(v is not None for v in [prompts, dialogue, direction, model_config, relations, duration])

    if status:
        gql = """
        mutation($shotId: String!, $status: String!, $blockerJson: String) {
          updateShotStatus(shotId: $shotId, status: $status, blockerJson: $blockerJson) {
            id shotId status
          }
        }"""
        variables: dict = {"shotId": shot_id, "status": status}
        if blocker:
            variables["blockerJson"] = blocker
        data = graphql(gql, variables)
        result = data.get("updateShotStatus", {})

        if json_mode and not has_shot_fields:
            print(as_json(result)); return
        print(f"  Shot {result.get('shotId')}: {result.get('status')}")

    if has_shot_fields:
        gql = """
        mutation($shotId: String!, $dialogue: String, $directionJson: String, $promptsJson: String, $modelConfigJson: String, $relationsJson: String, $targetDurationSec: Float) {
          updateFilmworkShot(shotId: $shotId, dialogue: $dialogue, directionJson: $directionJson, promptsJson: $promptsJson, modelConfigJson: $modelConfigJson, relationsJson: $relationsJson, targetDurationSec: $targetDurationSec) {
            id shotId status targetDurationSec
          }
        }"""
        variables = {"shotId": shot_id}
        if prompts is not None:
            variables["promptsJson"] = prompts
        if dialogue is not None:
            variables["dialogue"] = dialogue
        if direction is not None:
            variables["directionJson"] = direction
        if model_config is not None:
            variables["modelConfigJson"] = model_config
        if relations is not None:
            variables["relationsJson"] = relations
        if duration is not None:
            variables["targetDurationSec"] = duration
        data = graphql(gql, variables)
        result = data.get("updateFilmworkShot", {})

        if json_mode:
            print(as_json(result)); return

        updated = [k for k in ["prompts", "dialogue", "direction", "model-config", "relations", "duration"] if locals().get(k.replace("-", "_")) is not None]
        print(f"  Shot {result.get('shotId')}: updated {', '.join(updated)}")

    if not status and not has_shot_fields:
        print("Error: Provide at least one flag (--status, --prompts, --dialogue, --direction, --model-config, --relations, --duration)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Decisions & Insights
# ---------------------------------------------------------------------------

def add_decision(args: list[str], json_mode: bool = False) -> None:
    note_id = None; shot_id = None; action = None; reason = None; outcome = None

    i = 0
    while i < len(args):
        if args[i] == "--shot" and i + 1 < len(args):
            shot_id = args[i + 1]; i += 2
        elif args[i] == "--action" and i + 1 < len(args):
            action = args[i + 1]; i += 2
        elif args[i] == "--reason" and i + 1 < len(args):
            reason = args[i + 1]; i += 2
        elif args[i] == "--outcome" and i + 1 < len(args):
            outcome = args[i + 1]; i += 2
        elif not note_id:
            note_id = args[i]; i += 1
        else:
            i += 1

    if not all([note_id, action, reason, outcome]):
        print("Usage: nl.py decision <noteId> [--shot ID] --action A --reason R --outcome O"); return

    gql = """
    mutation($noteId: String!, $shotId: String, $actor: String!, $action: String!, $reason: String!, $outcome: String!) {
      addDecision(noteId: $noteId, shotId: $shotId, actor: $actor, action: $action, reason: $reason, outcome: $outcome) {
        id createdAt
      }
    }"""
    variables: dict = {
        "noteId": note_id, "actor": "agent",
        "action": action, "reason": reason, "outcome": outcome,
    }
    if shot_id:
        variables["shotId"] = shot_id

    data = graphql(gql, variables)
    result = data.get("addDecision", {})

    if json_mode:
        print(as_json(result)); return
    print(f"  Decision logged: {result.get('id')}")


def add_insight(args: list[str], json_mode: bool = False) -> None:
    note_id = None; category = None; tags = None; title = None; detail = None; source_shots = None

    i = 0
    while i < len(args):
        if args[i] == "--category" and i + 1 < len(args):
            category = args[i + 1]; i += 2
        elif args[i] == "--tags" and i + 1 < len(args):
            tags = args[i + 1]; i += 2
        elif args[i] == "--title" and i + 1 < len(args):
            title = args[i + 1]; i += 2
        elif args[i] == "--detail" and i + 1 < len(args):
            detail = args[i + 1]; i += 2
        elif args[i] == "--source-shots" and i + 1 < len(args):
            source_shots = args[i + 1]; i += 2
        elif not note_id:
            note_id = args[i]; i += 1
        else:
            i += 1

    if not all([note_id, category, tags, title, detail]):
        print("Usage: nl.py insight <noteId> --category C --tags T1,T2 --title T --detail D [--source-shots JSON]"); return

    import json as _json
    tags_list = [t.strip() for t in tags.split(",")]
    tags_json = _json.dumps(tags_list)

    gql = """
    mutation($noteId: String!, $category: String!, $tagsJson: String!, $title: String!, $detail: String!, $sourceShotsJson: String) {
      addInsight(noteId: $noteId, category: $category, tagsJson: $tagsJson, title: $title, detail: $detail, sourceShotsJson: $sourceShotsJson) {
        id category tagsJson title createdAt
      }
    }"""
    variables: dict = {"noteId": note_id, "category": category, "tagsJson": tags_json, "title": title, "detail": detail}
    if source_shots:
        variables["sourceShotsJson"] = source_shots

    data = graphql(gql, variables)
    result = data.get("addInsight", {})

    if json_mode:
        print(as_json(result)); return
    print(f"  Insight logged: {result.get('title')} ({result.get('id')})")


def list_decisions(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py decisions <noteId> [--shot ID] [--limit N] [--offset N]"); return

    note_id = args[0]
    shot_id = None; limit = None; offset = None

    i = 1
    while i < len(args):
        if args[i] == "--shot" and i + 1 < len(args):
            shot_id = args[i + 1]; i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1]); i += 2
        elif args[i] == "--offset" and i + 1 < len(args):
            offset = int(args[i + 1]); i += 2
        else:
            i += 1

    gql = """
    query($noteId: String!, $shotId: String, $limit: Int, $offset: Int) {
      filmworkDecisions(noteId: $noteId, shotId: $shotId, limit: $limit, offset: $offset) {
        id shotId actor action reason outcome createdAt
      }
    }"""
    variables: dict = {"noteId": note_id}
    if shot_id:
        variables["shotId"] = shot_id
    if limit is not None:
        variables["limit"] = limit
    if offset is not None:
        variables["offset"] = offset

    data = graphql(gql, variables)
    decisions = data.get("filmworkDecisions", [])

    if json_mode:
        print(as_json(decisions)); return

    if not decisions:
        print("  No decisions found."); return

    for d in decisions:
        shot = f"[{d.get('shotId', 'project')}] " if d.get("shotId") else ""
        print(f"  {shot}{d.get('action','')} — {d.get('reason','')}")
        if d.get("outcome"):
            print(f"    outcome: {d['outcome']}")
        print(f"    ({d.get('createdAt','')})")


def list_insights(args: list[str], json_mode: bool = False) -> None:
    note_id = None; category = None; tag = None; limit = None; offset = None

    i = 0
    while i < len(args):
        if args[i] == "--category" and i + 1 < len(args):
            category = args[i + 1]; i += 2
        elif args[i] == "--tag" and i + 1 < len(args):
            tag = args[i + 1]; i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1]); i += 2
        elif args[i] == "--offset" and i + 1 < len(args):
            offset = int(args[i + 1]); i += 2
        elif not note_id and not args[i].startswith("--"):
            note_id = args[i]; i += 1
        else:
            i += 1

    gql = """
    query($noteId: String, $category: String, $tag: String, $limit: Int, $offset: Int) {
      filmworkInsights(noteId: $noteId, category: $category, tag: $tag, limit: $limit, offset: $offset) {
        id noteId category tagsJson title detail createdAt
      }
    }"""
    variables: dict = {}
    if note_id:
        variables["noteId"] = note_id
    if category:
        variables["category"] = category
    if tag:
        variables["tag"] = tag
    if limit is not None:
        variables["limit"] = limit
    if offset is not None:
        variables["offset"] = offset

    data = graphql(gql, variables)
    insights = data.get("filmworkInsights", [])

    if json_mode:
        print(as_json(insights)); return

    if not insights:
        print("  No insights found."); return

    import json as _json
    for ins in insights:
        tags_str = ""
        try:
            tags = _json.loads(ins.get("tagsJson", "[]"))
            if tags:
                tags_str = f" ({', '.join(tags)})"
        except Exception:
            pass
        print(f"  [{ins.get('category','')}] {ins.get('title','')}{tags_str}")
        if ins.get("detail"):
            print(f"    {ins['detail'][:120]}")


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def provenance(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py provenance <assetId>"); return

    asset_id = args[0]
    gql = """
    query($assetId: String!) {
      assetProvenance(assetId: $assetId) {
        assetId method model prompt modelParamsJson userNote createdAt
        parents { id parentAssetId parentExternalRef role createdAt }
      }
    }"""
    data = graphql(gql, {"assetId": asset_id})
    prov = data.get("assetProvenance")

    if json_mode:
        print(as_json(prov)); return

    if not prov:
        print("  No provenance recorded for this asset."); return

    print(f"  Asset:   {prov['assetId']}")
    print(f"  Method:  {prov['method']}")
    if prov.get("model"):
        print(f"  Model:   {prov['model']}")
    if prov.get("prompt"):
        prompt_preview = prov["prompt"][:200] + ("..." if len(prov["prompt"]) > 200 else "")
        print(f"  Prompt:  {prompt_preview}")
    if prov.get("modelParamsJson"):
        print(f"  Params:  {prov['modelParamsJson']}")
    if prov.get("userNote"):
        print(f"  Note:    {prov['userNote']}")
    parents = prov.get("parents", [])
    if parents:
        print(f"  Parents ({len(parents)}):")
        for p in parents:
            if p.get("parentAssetId"):
                print(f"    [{p['role']}] asset:{p['parentAssetId']}")
            else:
                print(f"    [{p['role']}] ext:{p.get('parentExternalRef', '?')}")


def lineage(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py lineage <assetId> [--depth N]"); return

    asset_id = args[0]
    max_depth = 5
    if "--depth" in args:
        idx = args.index("--depth")
        if idx + 1 < len(args):
            max_depth = int(args[idx + 1])

    gql = """
    query($assetId: String!, $maxDepth: Int) {
      assetLineageTree(assetId: $assetId, maxDepth: $maxDepth) {
        id parentAssetId parentExternalRef role createdAt
      }
    }"""
    data = graphql(gql, {"assetId": asset_id, "maxDepth": max_depth})
    edges = data.get("assetLineageTree", [])

    if json_mode:
        print(as_json(edges)); return

    if not edges:
        print("  No lineage edges found."); return

    print(f"  Lineage edges ({len(edges)}):")
    for e in edges:
        if e.get("parentAssetId"):
            print(f"    [{e['role']}] asset:{e['parentAssetId']}")
        else:
            print(f"    [{e['role']}] ext:{e.get('parentExternalRef', '?')}")


def roll_snapshot(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py roll-snapshot <rollId>"); return

    roll_id = args[0]
    gql = """
    query($rollId: String!) {
      rollInputSnapshot(rollId: $rollId) {
        assetId assetType version
      }
    }"""
    data = graphql(gql, {"rollId": roll_id})
    snapshots = data.get("rollInputSnapshot", [])

    if json_mode:
        print(as_json(snapshots)); return

    if not snapshots:
        print("  No input snapshot recorded for this roll."); return

    print(f"  Input assets at generation time:")
    for s in snapshots:
        asset_ref = f" (id:{s['assetId']})" if s.get("assetId") else " (deleted)"
        print(f"    {s['assetType']} v{s['version']}{asset_ref}")


def set_provenance(args: list[str], json_mode: bool = False) -> None:
    asset_id = None
    method = None; model = None; prompt = None
    model_params = None; user_note = None
    parents_raw: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--method" and i + 1 < len(args):
            method = args[i + 1]; i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 2
        elif args[i] == "--prompt" and i + 1 < len(args):
            prompt = args[i + 1]; i += 2
        elif args[i] == "--model-params" and i + 1 < len(args):
            model_params = args[i + 1]; i += 2
        elif args[i] == "--user-note" and i + 1 < len(args):
            user_note = args[i + 1]; i += 2
        elif args[i] == "--parent" and i + 1 < len(args):
            parents_raw.append(args[i + 1]); i += 2
        elif not asset_id:
            asset_id = args[i]; i += 1
        else:
            i += 1

    if not asset_id or not method:
        print("Usage: nl.py set-provenance <assetId> --method M [--model M] [--prompt P] [--user-note N] [--parent JSON ...]"); return

    gql = """
    mutation($assetId: String!, $method: String!, $model: String, $prompt: String, $modelParamsJson: String, $userNote: String, $parents: [ProvenanceInputArg!]) {
      setAssetProvenance(assetId: $assetId, method: $method, model: $model, prompt: $prompt, modelParamsJson: $modelParamsJson, userNote: $userNote, parents: $parents) {
        assetId method model createdAt
        parents { parentAssetId parentExternalRef role }
      }
    }"""
    variables: dict = {"assetId": asset_id, "method": method}
    if model:
        variables["model"] = model
    if prompt:
        variables["prompt"] = prompt
    if model_params:
        variables["modelParamsJson"] = model_params
    if user_note:
        variables["userNote"] = user_note
    if parents_raw:
        variables["parents"] = [json.loads(p) for p in parents_raw]

    data = graphql(gql, variables)
    result = data.get("setAssetProvenance", {})

    if json_mode:
        print(as_json(result)); return

    parents = result.get("parents", [])
    print(f"  Provenance set: {result.get('method')} ({result.get('model', 'no model')})")
    if parents:
        print(f"  Parents: {len(parents)}")
        for p in parents:
            ref = p.get("parentAssetId") or p.get("parentExternalRef", "?")
            print(f"    [{p['role']}] {ref}")


def shot_create(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py shot-create <noteId> --label L [--duration N] [--status S] [--after LABEL]"); return

    note_id = args[0]
    label = None; duration = None; status = None; after = None

    i = 1
    while i < len(args):
        if args[i] == "--label" and i + 1 < len(args):
            label = args[i + 1]; i += 2
        elif args[i] == "--duration" and i + 1 < len(args):
            duration = float(args[i + 1]); i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]; i += 2
        elif args[i] == "--after" and i + 1 < len(args):
            after = args[i + 1]; i += 2
        else:
            i += 1

    if not label:
        print("Error: --label is required", file=sys.stderr); return

    # Determine sequenceOrder
    sequence_order = 999
    if after is not None:
        gql_ov = """
        query($noteId: String!) {
          filmworkOverview(noteId: $noteId) {
            shots { shotId }
          }
        }"""
        ov_data = graphql(gql_ov, {"noteId": note_id})
        ov = ov_data.get("filmworkOverview")
        if not ov:
            print(f"Filmwork not found: {note_id}", file=sys.stderr); return
        shots = ov.get("shots", [])
        shot_labels = [s.get("shotId", "") for s in shots]
        if after in shot_labels:
            after_idx = shot_labels.index(after)
            sequence_order = after_idx + 1  # insert right after (0-based index + 1 = 1-based position after)
        else:
            print(f"Warning: --after label '{after}' not found; appending at end.", file=sys.stderr)

    # Create the shot
    gql = """
    mutation($noteId: String!, $shotId: String!, $sequenceOrder: Int!) {
      createFilmworkShot(noteId: $noteId, shotId: $shotId, sequenceOrder: $sequenceOrder) {
        id status
      }
    }"""
    data = graphql(gql, {"noteId": note_id, "shotId": label, "sequenceOrder": sequence_order})
    created = data.get("createFilmworkShot", {})
    shot_uuid = created.get("id")

    if not shot_uuid:
        print("Error: Shot creation failed — no id returned", file=sys.stderr); return

    print(f"  Created shot {label} (id: {shot_uuid})")

    # Apply optional status / duration via shot_update
    update_args = [shot_uuid]
    if status and status != "not_started":
        update_args += ["--status", status]
    if duration is not None:
        update_args += ["--duration", str(duration)]

    if len(update_args) > 1:
        shot_update(update_args, json_mode=False)

    if json_mode:
        print(as_json({"id": shot_uuid, "shotId": label, "sequenceOrder": sequence_order,
                       "status": status or "not_started", "targetDurationSec": duration}))


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

_ASSET_EXT = {
    "start_frame": ".png", "end_frame": ".png", "keyframe": ".png",
    "ref_image": ".png", "dialogue": ".mp3", "sfx": ".mp3",
    "padded_audio": ".mp3", "ref_video": ".mp4",
}

_ASSET_PREFIX = {
    "start_frame": "FINAL", "end_frame": "FINAL",
    "sfx": "SFX", "dialogue": "DLG", "keyframe": "KF",
    "padded_audio": "PADDED", "ref_image": "REF", "ref_video": "REFVID",
}


def _asset_filename(shot_label: str, asset_type: str, label: str | None, version: int,
                    include_version: bool = False) -> str:
    prefix = _ASSET_PREFIX.get(asset_type, asset_type.upper())
    ext = _ASSET_EXT.get(asset_type, ".bin")
    vsuffix = f"_v{version}" if include_version else ""
    if label:
        safe_label = label.replace(" ", "_").replace("/", "_")
        return f"{shot_label}_{prefix}_{safe_label}{vsuffix}{ext}"
    if asset_type in ("start_frame", "end_frame"):
        return f"{shot_label}_{prefix}_{asset_type}{vsuffix}{ext}"
    return f"{shot_label}_{prefix}_v{version}{ext}"


def download_asset(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py download <assetId> <output_path>"); return

    asset_id = args[0]
    output_path = args[1]
    url = f"{BASE_URL}/api/filmwork/assets/{asset_id}/content"

    print(f"  Downloading {asset_id}...")
    download_binary(url, output_path)
    size = os.path.getsize(output_path)
    print(f"  Saved: {output_path} ({size:,} bytes)")

    if json_mode:
        print(as_json({"assetId": asset_id, "path": output_path, "size": size}))


def download_shot(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py download-shot <noteId> <label> [--dir D] [--all]"); return

    note_id, label = args[0], args[1]
    golden_only = "--all" not in args
    output_dir = "."
    if "--dir" in args:
        idx = args.index("--dir")
        if idx + 1 < len(args):
            output_dir = args[idx + 1]

    gql = """
    query($noteId: String!, $shotLabel: String!) {
      filmworkShotByLabel(noteId: $noteId, shotLabel: $shotLabel) {
        id shotId
        assets { id assetType label url version isGolden agentHold }
      }
    }"""
    data = graphql(gql, {"noteId": note_id, "shotLabel": label})
    s = data.get("filmworkShotByLabel")
    if not s:
        print(f"Shot {label} not found in {note_id}"); return

    assets = s.get("assets", [])
    if golden_only:
        assets = [a for a in assets if a.get("isGolden")]

    if not assets:
        qualifier = "golden " if golden_only else ""
        print(f"  No {qualifier}assets found for {label}.")
        if golden_only:
            print("  Use --all to download all versions.")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Detect duplicate type+label combos to add version suffix
    from collections import Counter
    type_label_counts = Counter((a["assetType"], a.get("label")) for a in assets if not a.get("agentHold"))
    needs_version = {k for k, v in type_label_counts.items() if v > 1}

    results = []
    for a in assets:
        if a.get("agentHold"):
            print(f"  [HOLD] Skipping {a['assetType']} {a.get('label', '')} (agent hold)")
            continue

        force_version = (a["assetType"], a.get("label")) in needs_version
        filename = _asset_filename(
            s.get("shotId", label), a["assetType"], a.get("label"), a.get("version", 1),
            include_version=force_version,
        )
        dest = os.path.join(output_dir, filename)
        url = f"{BASE_URL}/api/filmwork/assets/{a['id']}/content"

        print(f"  Downloading {a['assetType']}{' [' + a['label'] + ']' if a.get('label') else ''} → {filename}")
        download_binary(url, dest)
        size = os.path.getsize(dest)
        results.append({"assetId": a["id"], "type": a["assetType"], "file": filename, "size": size})

    print(f"\n  {len(results)} file(s) saved to {output_dir}")

    if json_mode:
        print(as_json(results))
