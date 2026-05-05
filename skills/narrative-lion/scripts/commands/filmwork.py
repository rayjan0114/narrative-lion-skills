"""Filmwork commands: overview, shot, preflight, upload, score, verdict, etc."""

import json
import mimetypes
import os
import sys

from lib.client import graphql, upload_binary
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

    # Step 3: Confirm
    gql_confirm = """
    mutation($shotId: String!, $assetKey: String!, $assetType: String!, $label: String) {
      confirmAssetUpload(shotId: $shotId, assetKey: $assetKey, assetType: $assetType, label: $label) {
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
        print("Usage: nl.py shot-update <shotId> [--status S] [--blocker JSON]"); return

    shot_id = args[0]
    status = None; blocker = None

    i = 1
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1]; i += 2
        elif args[i] == "--blocker" and i + 1 < len(args):
            blocker = args[i + 1]; i += 2
        else:
            i += 1

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

        if json_mode:
            print(as_json(result)); return
        print(f"  Shot {result.get('shotId')}: {result.get('status')}")
    else:
        print("Error: At least --status is required", file=sys.stderr)


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
    note_id = None; category = None; title = None; detail = None; source_shots = None

    i = 0
    while i < len(args):
        if args[i] == "--category" and i + 1 < len(args):
            category = args[i + 1]; i += 2
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

    if not all([note_id, category, title, detail]):
        print("Usage: nl.py insight <noteId> --category C --title T --detail D [--source-shots JSON]"); return

    gql = """
    mutation($noteId: String!, $category: String!, $title: String!, $detail: String!, $sourceShotsJson: String) {
      addInsight(noteId: $noteId, category: $category, title: $title, detail: $detail, sourceShotsJson: $sourceShotsJson) {
        id title createdAt
      }
    }"""
    variables: dict = {"noteId": note_id, "category": category, "title": title, "detail": detail}
    if source_shots:
        variables["sourceShotsJson"] = source_shots

    data = graphql(gql, variables)
    result = data.get("addInsight", {})

    if json_mode:
        print(as_json(result)); return
    print(f"  Insight logged: {result.get('title')} ({result.get('id')})")


def list_decisions(args: list[str], json_mode: bool = False) -> None:
    if not args:
        print("Usage: nl.py decisions <noteId> [--shot ID]"); return

    note_id = args[0]
    shot_id = None
    if "--shot" in args:
        idx = args.index("--shot")
        shot_id = args[idx + 1] if idx + 1 < len(args) else None

    gql = """
    query($noteId: String!, $shotId: String) {
      filmworkDecisions(noteId: $noteId, shotId: $shotId) {
        id shotId actor action reason outcome createdAt
      }
    }"""
    variables: dict = {"noteId": note_id}
    if shot_id:
        variables["shotId"] = shot_id

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
    if not args:
        print("Usage: nl.py insights <noteId> [--category C]"); return

    note_id = args[0]
    category = None
    if "--category" in args:
        idx = args.index("--category")
        category = args[idx + 1] if idx + 1 < len(args) else None

    gql = """
    query($noteId: String!, $category: String) {
      filmworkInsights(noteId: $noteId, category: $category) {
        id category title detail createdAt
      }
    }"""
    variables: dict = {"noteId": note_id}
    if category:
        variables["category"] = category

    data = graphql(gql, variables)
    insights = data.get("filmworkInsights", [])

    if json_mode:
        print(as_json(insights)); return

    if not insights:
        print("  No insights found."); return

    for ins in insights:
        print(f"  [{ins.get('category','')}] {ins.get('title','')}")
        if ins.get("detail"):
            print(f"    {ins['detail'][:120]}")
