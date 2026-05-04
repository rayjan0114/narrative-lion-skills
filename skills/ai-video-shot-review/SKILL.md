---
name: ai-video-shot-review
description: Debug an AI-generated video shot (Kling / Veo / Sora / Runway / etc.) by extracting strategic frames with ffmpeg, comparing against reference frames, scoring across 5 dimensions on a 55-point scale, and producing a production-readiness decision. Use when the user asks you to analyze / debug / score / review a generated video.
metadata:
  author: rayjan0114
  version: 1.0.0
user-invocable: true
---

# ai-video-shot-review Skill

## Purpose

Claude cannot play video directly, but it CAN read image frames. This skill bridges the gap: take a generated AI video output, extract frames at tactically chosen timestamps with ffmpeg, read them alongside reference start/end frames, and produce a weighted scorecard + production-readiness verdict so the user can decide whether to ship the shot, re-roll, or switch model.

## When to Use

Invoke this skill whenever:
- The user has a model output (Kling / Veo / Sora / Runway / Luma / Wan / Seedance / etc.) and wants to evaluate it
- The user mentions phrases like "review this video", "debug this shot", "score this", "analyze this output"
- The user is running an A/B model comparison test and has a new result
- The user wants to decide whether to commit to batch production with the current model

Do NOT invoke for:
- User wants to write a prompt (not reviewing output)
- User wants to plan a shot (nothing generated yet)
- Video is live-action footage (not AI-generated)

## Parameters

The user may pass:
- **Video path** — explicit path, or "in Downloads", or just the filename. If ambiguous, search `~/Downloads/` for recent video files.
- **Shot ID** — e.g. `05D`, `07A`. Optional, used to locate matching reference frames if a project structure exists.
- **Model name** — e.g. `kling-2.6`, `veo-3.1-lite`, `sora-2-pro`. Used in the output filename and scorecard label.
- **Reference frames** — start frame and/or end frame paths. If the user has a project with a known structure, look for them there. If not provided, skip the reference comparison and note it in the report.
- **Shot duration** — if not 10s, override timestamp defaults.

If the user doesn't supply these, infer from filename/context and confirm before extracting frames.

## Prerequisites

- **ffmpeg** must be installed (`ffmpeg -version` to verify). If missing, tell the user to install it and stop.

## Workflow

### Step 1: Locate the video file

If path is ambiguous, search Downloads for recent video files:

```bash
ls -lt ~/Downloads/*.mp4 2>/dev/null | head -10
```

Confirm the file with the user if more than one candidate.

### Step 2: Set up working directory

Create a directory for extracted frames next to the video, or in a user-specified location:

```bash
VIDEO_DIR="$(dirname "$VIDEO_PATH")"
WORK_DIR="${VIDEO_DIR}/review-frames"
mkdir -p "${WORK_DIR}"
```

If the user has a project structure with an experiments directory, use that instead.

### Step 3: Get video metadata

```bash
ffprobe -v error \
  -show_entries stream=codec_name,width,height,r_frame_rate,duration,nb_frames \
  -show_entries format=duration \
  -of default=noprint_wrappers=1 "$VIDEO_PATH"
```

Record: resolution, fps, duration, frame count, whether audio stream is present.

### Step 4: Extract frames strategically

Three purpose-driven frame sets. Scale to ~942x550 for fast reading while preserving detail.

**4.1 Overview frames (1 fps across full duration)**

Purpose: judge overall flow, pose transitions, BG changes, high-level stability.

```bash
ffmpeg -y -i "$VIDEO_PATH" \
  -vf "fps=1,scale=942:550" \
  "${WORK_DIR}/overview_%02d.png"
```

**4.2 Critical-motion frames (8 fps, 1 second window)**

Purpose: verify whether a short articulation or gesture actually occurred. Window should center on the most important beat in the shot.

```bash
# Example: if the critical moment is at 1.0s, sample 0.7s-1.7s at 8fps
ffmpeg -y -ss 0.7 -i "$VIDEO_PATH" \
  -t 1.0 -vf "fps=8,scale=942:550" \
  "${WORK_DIR}/detail_%02d.png"
```

For shots with spoken dialogue, center on the dialogue beat.
For shots with no dialogue, center on the key gesture or expression change.

**4.3 End-stage stability frames (4 fps, last ~2.5s)**

Purpose: check late-stage morphing, finger drift, face collapse. Failures often appear only in the final seconds.

```bash
# For a 10s video, sample 7.5s-10s at 4fps
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO_PATH")
START=$(echo "$DURATION - 2.5" | bc)
ffmpeg -y -ss "$START" -i "$VIDEO_PATH" \
  -t 2.5 -vf "fps=4,scale=942:550" \
  "${WORK_DIR}/end_%02d.png"
```

Adjust timestamps proportionally for non-10s shots.

### Step 5: Read reference frames (if available)

If the user provided reference start/end frames, read them for comparison. If the user has a project structure, look for them there.

If no reference frames are available, skip this step and note in the report that scoring is based on internal consistency only.

### Step 6: Read all extracted frames

Read all overview, detail, and end frames in parallel (single message, many Read tool calls). Preserve order so you can reason about temporal flow.

### Step 7: Analyze & score

Score across 5 weighted dimensions totaling 55 points.

| Dimension | Weight | Max | What to look for |
|---|---|---|---|
| **Face consistency** | x3 | 15 | Identity stability across all frames. Same eyes, nose, features. Penalize: face morph, identity drift, eye shape change, jaw migration. |
| **Micro-expression fidelity** | x3 | 15 | Does the actual performance match the intended emotion/action? Penalize: wrong valence, missed beats, generic "pleasant" default, model softening. |
| **Drift / morph control** | x2 | 10 | Structural integrity of hands, fingers, props, clothing. Penalize: extra fingers, hand warping, prop morphing, clothing glitch. |
| **Full-duration stability** | x2 | 10 | Does the shot hold together across the full duration? Penalize: late-stage collapse, accumulating drift, motion that starts fine then derails. |
| **Color / style match** | x1 | 5 | Visual style preserved throughout. Penalize: style drift (e.g. 2D to 3D), oversaturation, lighting inconsistency. |

Compute weighted total out of 55.

For each dimension, produce 1-2 concrete frame-specific callouts (e.g. "detail_03 shows lip flutter not matching intended locked expression", "end_07 shows left index finger briefly merging with middle finger").

### Step 8: Decision matrix

| Score | Verdict | Action |
|---|---|---|
| **>= 45** | Golden | Lock model + seed; proceed to production. |
| **40 - 44** | Viable | Ship this shot, but consider one comparison with a stronger model for critical shots. |
| **30 - 39** | Marginal | Re-roll with tightened prompt, or try a different model. |
| **< 30** | Fail | Do not use. Switch model, rework prompt, or rework reference frames. |

### Step 9: Produce the report

Output format:

```markdown
# <Model> Debug Scorecard -- Shot <ShotID> (<Variant>)

## TL;DR
<2-3 sentence verdict with score and the single most important finding>

## Frame-by-frame observations
### Overview (0-Ns)
<table: timestamp | what happens>

### Critical motion window
<did the intended action happen? concrete pass/fail>

### End stage
<late-stage stability verdict>

## Scorecard

| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Face consistency | x3 | X/15 | ... |
| Micro-expression | x3 | X/15 | ... |
| Drift / morph | x2 | X/10 | ... |
| Stability | x2 | X/10 | ... |
| Style | x1 | X/5 | ... |
| **Total** | | **X/55** | |

## Critical production notes
<concrete issues the user needs to act on>

## Recommended next moves
### Immediate
<ship / re-roll / switch model>
### Follow-up
<A/B test suggestion if score is in the 30-44 band>
```

## Tips & gotchas

- **Score the model against the brief, not the brief itself.** If the intended emotion is wrong, that's a creative decision issue, not a model failure.
- **BG mismatch between start and end frames**: this is a reference-frame problem, not a model failure. Flag it but don't penalize the model for faithfully interpolating between mismatched keyframes.
- **Prop missing from output** (e.g. object in prompt but not in reference frames): the model cannot instantiate things that don't exist in the input. Score the input setup, not the model.
- **Mouth never moves for a scripted line**: expected for models without native audio generation. Note that lip-sync post-processing will be required. Do not penalize under "drift".
- **Mouth moves CONTINUOUSLY when it should be still**: this IS a model failure (the "liveliness bias" problem). Penalize under Micro-expression fidelity.
- **Reading 28+ frames in parallel**: do it in a single message with many Read tool calls. Do not read them one at a time.
- **Scoring calibration**: 55/55 means the model perfectly executed a difficult brief with no drift. 45-50 is already excellent. Most first-run outputs land 35-42.
- **The scorecard is advisory**: the user's eye is the final judge. Present numbers, but explain reasoning so they can override.
