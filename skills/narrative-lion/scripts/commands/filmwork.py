"""Filmwork commands: overview, shot, preflight, upload, score, verdict, etc."""

from __future__ import annotations

import difflib
import json
import mimetypes
import os
import sys
import textwrap

from lib.client import graphql, upload_binary, download_binary, BASE_URL
from lib.formatters import as_json, status_bar


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def overview(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py overview <noteId>", file=sys.stderr); return
    note_id = args[0]

    gql = """
    query($noteId: String!) {
      filmworkOverview(noteId: $noteId) {
        noteId title totalShots
        statusCounts { notStarted assetPrep ready generating review done blocked }
        shots {
          shotId status lastDecisionAt
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
        print(f"Filmwork not found: {note_id}", file=sys.stderr); return

    if json_mode:
        print(as_json(ov)); return

    counts = ov.get("statusCounts", {})
    total = ov.get("totalShots", 0)
    print(f"{ov.get('title', '')}")
    print(f"  {status_bar(counts, total)}")
    print()

    shots = ov.get("shots", [])
    print(f"  {'Shot':<6} {'Status':<12} {'Assets':<8} {'Rolls':<8} {'Best':<6} {'PF':<4} {'Dec'}")
    print(f"  {'----':<6} {'------':<12} {'------':<8} {'-----':<8} {'----':<6} {'--':<4} {'---'}")
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
        last_dec = s.get("lastDecisionAt")
        dec = last_dec[:10] if last_dec else ("-" if status == "not_started" else "!")
        print(f"  {label:<6} {status:<12} {asset_total:<8} {roll_total:<8} {best:<6} {ready:<4} {dec}")

    links = ov.get("linkedNotes", [])
    if links:
        print(f"\n  Linked Notes:")
        for ln in links:
            print(f"    [{ln.get('linkType','')}] {ln.get('targetNoteTitle','?')} ({ln.get('targetNoteId','')})")


def shot(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py shot <noteId> <label>", file=sys.stderr); return
    note_id, label = args[0], args[1]

    gql = """
    query($noteId: String!, $shotLabel: String!) {
      filmworkShotByLabel(noteId: $noteId, shotLabel: $shotLabel) {
        id shotId status targetDurationSec dialogue
        directionJson promptsJson modelConfigJson blockerJson
        lastActivityAt lastDecisionAt
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
        print(f"Shot {label} not found in {note_id}", file=sys.stderr); return

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

    last_dec = s.get("lastDecisionAt")
    if last_dec:
        print(f"  Last decision: {last_dec[:16]}")
    elif s.get("status") != "not_started":
        print(f"  Last decision: NONE — log decisions to aid debugging")

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
        print("Usage: nl.py preflight <noteId> <label>", file=sys.stderr); return
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
        print(f"Shot {label} not found", file=sys.stderr); return

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
        print("Usage: nl.py upload <shotId> <assetType> <file> [--label L]", file=sys.stderr); return

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
    print(f"  Uploading {filename}...", file=sys.stderr)
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
        print("Usage: nl.py upload-roll <shotId> <file> --seed N --model M --prompt-version N", file=sys.stderr); return

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
    print(f"  Uploading {filename}...", file=sys.stderr)
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
        print("Usage: nl.py score <rollId> --face N --expr N --motion N --stability N --style N", file=sys.stderr); return

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
        print("Usage: nl.py verdict <rollId> <approved|rejected>", file=sys.stderr); return

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
        print("Usage: nl.py golden-roll <rollId>", file=sys.stderr); return

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
        print("Usage: nl.py shot-update <shotId> [--status S] [--blocker JSON] [--prompts JSON] [--dialogue JSON] [--direction JSON] [--model-config JSON] [--relations JSON] [--duration N]", file=sys.stderr); return

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

    status_result = None
    fields_result = None

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
        status_result = data.get("updateShotStatus", {})
        if not json_mode:
            print(f"  Shot {status_result.get('shotId')}: {status_result.get('status')}")

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
        fields_result = data.get("updateFilmworkShot", {})

        if not json_mode:
            updated = [k for k in ["prompts", "dialogue", "direction", "model-config", "relations", "duration"] if locals().get(k.replace("-", "_")) is not None]
            print(f"  Shot {fields_result.get('shotId')}: updated {', '.join(updated)}")

    if json_mode:
        if status_result and fields_result:
            print(as_json({"status": status_result, "fields": fields_result}))
        elif status_result:
            print(as_json(status_result))
        elif fields_result:
            print(as_json(fields_result))
        return

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
        print("Usage: nl.py decision <noteId> [--shot ID] --action A --reason R --outcome O", file=sys.stderr); return

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
        print("Usage: nl.py insight <noteId> --category C --tags T1,T2 --title T --detail D [--source-shots JSON]", file=sys.stderr); return

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
        print("Usage: nl.py decisions <noteId> [--shot ID] [--limit N] [--offset N]", file=sys.stderr); return

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
        print("Usage: nl.py provenance <assetId>", file=sys.stderr); return

    asset_id = args[0]
    gql = """
    query($assetId: String!) {
      assetProvenance(assetId: $assetId) {
        assetId method model prompt modelParamsJson userNote createdAt
        parents { id childAssetId parentAssetId parentExternalRef role createdAt }
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
        print("  Prompt:")
        print(textwrap.fill(prov["prompt"], width=100, initial_indent="    ", subsequent_indent="    "))
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
        print("Usage: nl.py lineage <assetId> [--depth N]", file=sys.stderr); return

    asset_id = args[0]
    max_depth = 5
    if "--depth" in args:
        idx = args.index("--depth")
        if idx + 1 < len(args):
            max_depth = int(args[idx + 1])

    gql = """
    query($assetId: String!, $maxDepth: Int) {
      assetLineageTree(assetId: $assetId, maxDepth: $maxDepth) {
        id childAssetId parentAssetId parentExternalRef role createdAt
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
        child = (e.get("childAssetId") or "?")[:12]
        if e.get("parentAssetId"):
            parent = e["parentAssetId"][:12]
            print(f"    {parent}.. --[{e['role']}]--> {child}..")
        else:
            print(f"    ext:{(e.get('parentExternalRef') or '?')} --[{e['role']}]--> {child}..")


def roll_snapshot(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py roll-snapshot <rollId>", file=sys.stderr); return

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


def prompt_view(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py prompt <noteId> <shotLabel> [--version N]", file=sys.stderr); return

    note_id = args[0]
    shot_label = args[1]
    version = None
    if "--version" in args:
        idx = args.index("--version")
        if idx + 1 < len(args):
            try:
                version = int(args[idx + 1])
            except ValueError:
                print("Error: --version must be an integer", file=sys.stderr); return

    gql = """
    query($noteId: String!, $shotLabel: String!) {
      filmworkShotByLabel(noteId: $noteId, shotLabel: $shotLabel) {
        shotId promptsJson
      }
    }"""
    data = graphql(gql, {"noteId": note_id, "shotLabel": shot_label})
    s = data.get("filmworkShotByLabel")
    if not s:
        print(f"Shot {shot_label} not found in {note_id}", file=sys.stderr); return

    prompts_raw = s.get("promptsJson")
    if not prompts_raw:
        if json_mode:
            print(as_json([])); return
        print("  No prompts defined for this shot."); return

    try:
        prompts = json.loads(prompts_raw)
    except (json.JSONDecodeError, TypeError):
        if json_mode:
            print(as_json({"error": "promptsJson is not valid JSON"})); return
        print("  Error: promptsJson is not valid JSON."); return

    if json_mode:
        print(as_json(prompts)); return

    if version is not None:
        match = next((p for p in prompts if p.get("version") == version), None)
        if not match:
            available = [p.get("version") for p in prompts]
            print(f"  Version {version} not found. Available: {available}"); return
        active = " [ACTIVE]" if match.get("isActive") else ""
        print(f"  Prompt v{version}{active}  ({s.get('shotId')})")
        print()
        print(textwrap.fill(match.get("body", ""), width=100, initial_indent="  ", subsequent_indent="  "))
        if match.get("negativePrompt"):
            print()
            print("  Negative:")
            print(textwrap.fill(match["negativePrompt"], width=100, initial_indent="    ", subsequent_indent="    "))
        if match.get("modelTarget"):
            print(f"\n  Model target: {match['modelTarget']}")
    else:
        print(f"  Prompts for shot {s.get('shotId')} ({len(prompts)} version(s)):")
        print()
        for p in prompts:
            v = p.get("version", "?")
            active = " [ACTIVE]" if p.get("isActive") else ""
            body = p.get("body", "")
            first_line = body.split("\n")[0][:80]
            ellipsis = "..." if len(body.split("\n")[0]) > 80 or len(body.split("\n")) > 1 else ""
            print(f"  v{v}{active}: {first_line}{ellipsis}")


def roll_context(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py roll-context <rollId>", file=sys.stderr); return

    roll_id = args[0]
    gql = """
    query($rollId: String!) {
      rollContext(rollId: $rollId) {
        id rollNumber shotId shotLabel seed modelUsed promptVersion
        totalScore verdict isGolden generatedAt scorecardJson issues
        promptBody promptNegative
        inputs { assetType label version assetId method model }
      }
    }"""
    data = graphql(gql, {"rollId": roll_id})
    rc = data.get("rollContext")

    if json_mode:
        print(as_json(rc)); return

    if not rc:
        print("  Roll not found."); return

    golden = " [GOLDEN]" if rc.get("isGolden") else ""
    print(f"Roll #{rc['rollNumber']} -- {rc['shotLabel']} (shot: {rc['shotId'][:12]}..){golden}")
    print(f"  Verdict:   {rc['verdict']}")
    print(f"  Score:     {rc.get('totalScore') or '-'}")
    print(f"  Model:     {rc.get('modelUsed') or '?'}  seed={rc.get('seed') or '?'}  prompt_v={rc.get('promptVersion') or '?'}")
    print(f"  Generated: {rc.get('generatedAt', '')[:16]}")

    if rc.get("issues"):
        print(f"  Issues:    {rc['issues']}")

    if rc.get("promptBody"):
        print(f"\n  Prompt (v{rc.get('promptVersion') or '?'}):")
        print(textwrap.fill(rc["promptBody"], width=100, initial_indent="    ", subsequent_indent="    "))
    if rc.get("promptNegative"):
        print(f"\n  Negative:")
        print(textwrap.fill(rc["promptNegative"], width=100, initial_indent="    ", subsequent_indent="    "))

    inputs = rc.get("inputs", [])
    if inputs:
        print(f"\n  Input Assets ({len(inputs)}):")
        for inp in inputs:
            label_str = f" [{inp['label']}]" if inp.get("label") else ""
            asset_ref = f" id:{inp['assetId'][:12]}.." if inp.get("assetId") else " (deleted)"
            prov_str = ""
            if inp.get("method"):
                prov_str = f" via {inp['method']}"
                if inp.get("model"):
                    prov_str += f"/{inp['model']}"
            print(f"    {inp['assetType']}{label_str} v{inp['version']}{asset_ref}{prov_str}")


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
        print("Usage: nl.py set-provenance <assetId> --method M [--model M] [--prompt P] [--user-note N] [--parent JSON ...]", file=sys.stderr); return

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
        print("Usage: nl.py shot-create <noteId> [--label L] [--after LABEL] [--duration N] [--status S]", file=sys.stderr); return

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

    if not label and not after:
        print("Error: either --label L or --after LABEL is required", file=sys.stderr); return

    if after and not label:
        # Auto-label mode: backend computes label + sequenceOrder
        gql = """
        mutation($noteId: String!, $afterLabel: String!) {
          createFilmworkShot(noteId: $noteId, afterLabel: $afterLabel) {
            id shotId sequenceOrder status
          }
        }"""
        data = graphql(gql, {"noteId": note_id, "afterLabel": after})
        created = data.get("createFilmworkShot", {})
        shot_uuid = created.get("id")
        if not shot_uuid:
            print("Error: Shot creation failed — no id returned", file=sys.stderr); return
        if not json_mode:
            print(f"  Created shot {created.get('shotId', '?')} (id: {shot_uuid}, after: {after})")
    else:
        # Manual mode: --label provided, sequenceOrder from --after or default
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
                sequence_order = after_idx + 1
            else:
                print(f"Warning: --after label '{after}' not found; appending at end.", file=sys.stderr)

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
        if not json_mode:
            print(f"  Created shot {label} (id: {shot_uuid})")

    # Apply optional status / duration via shot_update
    update_args = [shot_uuid]
    if status and status != "not_started":
        update_args += ["--status", status]
    if duration is not None:
        update_args += ["--duration", str(duration)]

    if len(update_args) > 1:
        if json_mode:
            _saved = sys.stdout
            sys.stdout = sys.stderr
            try:
                shot_update(update_args, json_mode=False)
            finally:
                sys.stdout = _saved
        else:
            shot_update(update_args, json_mode=False)

    if json_mode:
        print(as_json(created))


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
        print("Usage: nl.py download <assetId> <output_path>", file=sys.stderr); return

    asset_id = args[0]
    output_path = args[1]
    url = f"{BASE_URL}/api/filmwork/assets/{asset_id}/content"

    print(f"  Downloading {asset_id}...", file=sys.stderr)
    download_binary(url, output_path)
    size = os.path.getsize(output_path)
    print(f"  Saved: {output_path} ({size:,} bytes)", file=sys.stderr)

    if json_mode:
        print(as_json({"assetId": asset_id, "path": output_path, "size": size})); return


def download_shot(args: list[str], json_mode: bool = False) -> None:
    if len(args) < 2:
        print("Usage: nl.py download-shot <noteId> <label> [--dir D] [--all]", file=sys.stderr); return

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
        print(f"Shot {label} not found in {note_id}", file=sys.stderr); return

    assets = s.get("assets", [])
    if golden_only:
        assets = [a for a in assets if a.get("isGolden")]

    if not assets:
        qualifier = "golden " if golden_only else ""
        if json_mode:
            print(as_json([])); return
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
            print(f"  [HOLD] Skipping {a['assetType']} {a.get('label', '')} (agent hold)", file=sys.stderr)
            continue

        force_version = (a["assetType"], a.get("label")) in needs_version
        filename = _asset_filename(
            s.get("shotId", label), a["assetType"], a.get("label"), a.get("version", 1),
            include_version=force_version,
        )
        dest = os.path.join(output_dir, filename)
        url = f"{BASE_URL}/api/filmwork/assets/{a['id']}/content"

        print(f"  Downloading {a['assetType']}{' [' + a['label'] + ']' if a.get('label') else ''} → {filename}", file=sys.stderr)
        download_binary(url, dest)
        size = os.path.getsize(dest)
        results.append({"assetId": a["id"], "type": a["assetType"], "file": filename, "size": size})

    print(f"\n  {len(results)} file(s) saved to {output_dir}", file=sys.stderr)

    if json_mode:
        print(as_json(results)); return


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

_ANSI_RED = "\033[31m"
_ANSI_GREEN = "\033[32m"
_ANSI_CYAN = "\033[36m"
_ANSI_DIM = "\033[2m"
_ANSI_BOLD = "\033[1m"
_ANSI_RESET = "\033[0m"


def _use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _colorize_diff(lines: list[str]) -> list[str]:
    if not _use_color():
        return lines
    out = []
    for line in lines:
        if line.startswith("---") or line.startswith("+++"):
            out.append(f"{_ANSI_BOLD}{line}{_ANSI_RESET}")
        elif line.startswith("@@"):
            out.append(f"{_ANSI_CYAN}{line}{_ANSI_RESET}")
        elif line.startswith("-"):
            out.append(f"{_ANSI_RED}{line}{_ANSI_RESET}")
        elif line.startswith("+"):
            out.append(f"{_ANSI_GREEN}{line}{_ANSI_RESET}")
        else:
            out.append(line)
    return out


def _wrap_for_diff(text: str, width: int = 80) -> list[str]:
    """Wrap long text into lines for readable diffs."""
    lines = []
    for paragraph in text.split("\n"):
        if len(paragraph) <= width:
            lines.append(paragraph)
        else:
            lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def _fetch_prompts(note_id: str, shot_label: str) -> list[dict] | None:
    gql = """
    query($noteId: String!, $shotLabel: String!) {
      filmworkShotByLabel(noteId: $noteId, shotLabel: $shotLabel) {
        shotId promptsJson
      }
    }"""
    data = graphql(gql, {"noteId": note_id, "shotLabel": shot_label})
    s = data.get("filmworkShotByLabel")
    if not s:
        print(f"Shot {shot_label} not found in {note_id}", file=sys.stderr)
        return None
    raw = s.get("promptsJson")
    if not raw:
        print("No prompts defined for this shot.", file=sys.stderr)
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        print("Error: promptsJson is not valid JSON.", file=sys.stderr)
        return None


def prompt_diff(args: list[str], json_mode: bool = False) -> None:
    """Compare two prompt versions side by side with unified diff."""
    if len(args) < 2:
        print("Usage: nl.py prompt-diff <noteId> <shotLabel> --from N --to M", file=sys.stderr); return

    note_id = args[0]
    shot_label = args[1]
    from_v: int | None = None
    to_v: int | None = None

    i = 2
    while i < len(args):
        if args[i] == "--from" and i + 1 < len(args):
            from_v = int(args[i + 1]); i += 2
        elif args[i] == "--to" and i + 1 < len(args):
            to_v = int(args[i + 1]); i += 2
        else:
            i += 1

    if from_v is None or to_v is None:
        print("Error: both --from N and --to M are required.", file=sys.stderr); return

    prompts = _fetch_prompts(note_id, shot_label)
    if prompts is None:
        return

    old = next((p for p in prompts if p.get("version") == from_v), None)
    new = next((p for p in prompts if p.get("version") == to_v), None)

    if not old:
        print(f"Version {from_v} not found. Available: {[p.get('version') for p in prompts]}", file=sys.stderr); return
    if not new:
        print(f"Version {to_v} not found. Available: {[p.get('version') for p in prompts]}", file=sys.stderr); return

    if json_mode:
        print(as_json({"from": old, "to": new})); return

    old_model = old.get("modelTarget", "?")
    new_model = new.get("modelTarget", "?")

    # Header
    print(f"  Prompt diff: v{from_v} -> v{to_v}  ({shot_label})")
    if old_model != new_model:
        print(f"  Model: {old_model} -> {new_model}")
    print()

    # Body diff
    old_lines = _wrap_for_diff(old.get("body", ""))
    new_lines = _wrap_for_diff(new.get("body", ""))
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"prompt v{from_v} ({old_model})",
        tofile=f"prompt v{to_v} ({new_model})",
        lineterm="",
    ))

    if diff:
        for line in _colorize_diff(diff):
            print(f"  {line}")
    else:
        print("  (body unchanged)")

    # Negative prompt diff
    old_neg = old.get("negativePrompt", "")
    new_neg = new.get("negativePrompt", "")
    if old_neg != new_neg:
        print()
        old_neg_lines = _wrap_for_diff(old_neg) if old_neg else ["(none)"]
        new_neg_lines = _wrap_for_diff(new_neg) if new_neg else ["(none)"]
        neg_diff = list(difflib.unified_diff(
            old_neg_lines, new_neg_lines,
            fromfile="negative v" + str(from_v),
            tofile="negative v" + str(to_v),
            lineterm="",
        ))
        if neg_diff:
            for line in _colorize_diff(neg_diff):
                print(f"  {line}")


def _fetch_roll_context(roll_id: str) -> dict | None:
    gql = """
    query($rollId: String!) {
      rollContext(rollId: $rollId) {
        id rollNumber shotId shotLabel seed modelUsed promptVersion
        totalScore verdict isGolden generatedAt scorecardJson
        promptBody promptNegative
        inputs { assetType label version assetId method model }
      }
    }"""
    data = graphql(gql, {"rollId": roll_id})
    return data.get("rollContext")


def roll_diff(args: list[str], json_mode: bool = False) -> None:
    """Compare two rolls: metadata, prompt, and input assets."""
    if len(args) < 2:
        print("Usage: nl.py roll-diff <rollId-A> <rollId-B>", file=sys.stderr); return

    roll_a_id = args[0]
    roll_b_id = args[1]

    a = _fetch_roll_context(roll_a_id)
    b = _fetch_roll_context(roll_b_id)

    if not a:
        print(f"Roll not found: {roll_a_id}", file=sys.stderr); return
    if not b:
        print(f"Roll not found: {roll_b_id}", file=sys.stderr); return

    if json_mode:
        print(as_json({"a": a, "b": b})); return

    color = _use_color()

    def _changed(label: str, va: str, vb: str) -> None:
        if va == vb:
            print(f"  {label:<12} {va}")
        else:
            arrow = f"{va} -> {vb}"
            if color:
                arrow = f"{_ANSI_RED}{va}{_ANSI_RESET} -> {_ANSI_GREEN}{vb}{_ANSI_RESET}"
            print(f"  {label:<12} {arrow}")

    # Header
    ga = " [GOLDEN]" if a.get("isGolden") else ""
    gb = " [GOLDEN]" if b.get("isGolden") else ""
    print(f"  Roll #{a['rollNumber']}{ga} vs Roll #{b['rollNumber']}{gb}  ({a.get('shotLabel', '?')})")
    print(f"  {'─' * 50}")

    # Metadata comparison
    _changed("Model", a.get("modelUsed") or "?", b.get("modelUsed") or "?")
    _changed("Seed", str(a.get("seed") or "?"), str(b.get("seed") or "?"))
    _changed("Prompt", f"v{a.get('promptVersion') or '?'}", f"v{b.get('promptVersion') or '?'}")
    _changed("Verdict", a.get("verdict", "?"), b.get("verdict", "?"))

    # Score comparison with delta
    sa = a.get("totalScore")
    sb = b.get("totalScore")
    sa_str = str(sa) if sa is not None else "-"
    sb_str = str(sb) if sb is not None else "-"
    if sa is not None and sb is not None and sa != sb:
        delta = sb - sa
        sign = "+" if delta > 0 else ""
        delta_str = f" ({sign}{delta})"
        if color:
            delta_color = _ANSI_GREEN if delta > 0 else _ANSI_RED
            print(f"  {'Score':<12} {_ANSI_RED}{sa_str}{_ANSI_RESET} -> {_ANSI_GREEN}{sb_str}{_ANSI_RESET}{delta_color}{delta_str}{_ANSI_RESET}")
        else:
            print(f"  {'Score':<12} {sa_str} -> {sb_str}{delta_str}")
    else:
        _changed("Score", sa_str, sb_str)

    # Scorecard breakdown if available
    sc_a = _parse_scorecard(a.get("scorecardJson"))
    sc_b = _parse_scorecard(b.get("scorecardJson"))
    if sc_a and sc_b:
        dims = ["faceLikeness", "expression", "motionNatural", "stability", "styleMatch"]
        dim_labels = {"faceLikeness": "face", "expression": "expr", "motionNatural": "motion", "stability": "stab", "styleMatch": "style"}
        parts = []
        for d in dims:
            va = sc_a.get(d, "?")
            vb = sc_b.get(d, "?")
            if va != vb:
                parts.append(f"{dim_labels[d]}:{va}->{vb}")
            else:
                parts.append(f"{dim_labels[d]}:{va}")
        print(f"  {'Scorecard':<12} {', '.join(parts)}")

    # Prompt diff
    body_a = a.get("promptBody") or ""
    body_b = b.get("promptBody") or ""
    if body_a != body_b:
        print(f"\n  {'─' * 20} Prompt Diff {'─' * 20}")
        diff_lines = list(difflib.unified_diff(
            _wrap_for_diff(body_a), _wrap_for_diff(body_b),
            fromfile=f"Roll #{a['rollNumber']} prompt v{a.get('promptVersion', '?')}",
            tofile=f"Roll #{b['rollNumber']} prompt v{b.get('promptVersion', '?')}",
            lineterm="",
        ))
        for line in _colorize_diff(diff_lines):
            print(f"  {line}")

    # Negative prompt diff
    neg_a = a.get("promptNegative") or ""
    neg_b = b.get("promptNegative") or ""
    if neg_a != neg_b:
        print(f"\n  {'─' * 20} Negative Diff {'─' * 18}")
        neg_diff = list(difflib.unified_diff(
            _wrap_for_diff(neg_a) if neg_a else ["(none)"],
            _wrap_for_diff(neg_b) if neg_b else ["(none)"],
            fromfile=f"Roll #{a['rollNumber']}", tofile=f"Roll #{b['rollNumber']}",
            lineterm="",
        ))
        for line in _colorize_diff(neg_diff):
            print(f"  {line}")

    # Input assets diff
    inputs_a = a.get("inputs", [])
    inputs_b = b.get("inputs", [])
    if inputs_a or inputs_b:
        print(f"\n  {'─' * 20} Input Assets {'─' * 19}")
        map_a = {inp["assetType"] + (f"[{inp['label']}]" if inp.get("label") else ""): inp for inp in inputs_a}
        map_b = {inp["assetType"] + (f"[{inp['label']}]" if inp.get("label") else ""): inp for inp in inputs_b}
        all_keys = list(dict.fromkeys(list(map_a.keys()) + list(map_b.keys())))

        for key in all_keys:
            ia = map_a.get(key)
            ib = map_b.get(key)
            if ia and ib:
                va_str = f"v{ia['version']}"
                vb_str = f"v{ib['version']}"
                prov_a = f" ({ia.get('method', '?')}" + (f"/{ia['model']}" if ia.get("model") else "") + ")"
                prov_b = f" ({ib.get('method', '?')}" + (f"/{ib['model']}" if ib.get("model") else "") + ")"
                if ia["version"] == ib["version"] and ia.get("assetId") == ib.get("assetId"):
                    dim = f"{_ANSI_DIM}(same){_ANSI_RESET}" if color else "(same)"
                    print(f"    {key:<20} {va_str}{prov_a} {dim}")
                else:
                    if color:
                        print(f"    {key:<20} {_ANSI_RED}{va_str}{prov_a}{_ANSI_RESET} -> {_ANSI_GREEN}{vb_str}{prov_b}{_ANSI_RESET}")
                    else:
                        print(f"    {key:<20} {va_str}{prov_a} -> {vb_str}{prov_b}")
            elif ia and not ib:
                if color:
                    print(f"    {_ANSI_RED}- {key:<18} v{ia['version']}{_ANSI_RESET}")
                else:
                    print(f"    - {key:<18} v{ia['version']}")
            else:
                if color:
                    print(f"    {_ANSI_GREEN}+ {key:<18} v{ib['version']}{_ANSI_RESET}")
                else:
                    print(f"    + {key:<18} v{ib['version']}")


def _parse_scorecard(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        sc = json.loads(raw)
        return sc.get("scores", {})
    except (json.JSONDecodeError, TypeError):
        return None
