---
name: nl-video-score
description: >
  Review and score AI-generated video shots (Kling / Veo / Sora / Runway / Luma / Wan / Seedance / etc.)
  by extracting strategic frames with ffmpeg, scoring across 5 weighted dimensions on a 55-point scale,
  and producing a production-readiness verdict. Use when the user wants to evaluate, debug, or score
  a generated video output.
metadata:
  author: rayjan0114
  version: 1.0.0
---

# NL Video Score

Claude cannot play video, but it CAN read image frames. This skill extracts frames at tactical timestamps, compares them against reference frames (if provided), and produces a weighted scorecard so the user can decide: ship, re-roll, or switch model.

## Prerequisites

ffmpeg must be installed. Verify: `ffmpeg -version`

## Workflow

### 1. Get video metadata

```bash
ffprobe -v error \
  -show_entries stream=codec_name,width,height,r_frame_rate,duration,nb_frames \
  -show_entries format=duration \
  -of default=noprint_wrappers=1 <video>
```

### 2. Extract frames — three-tier strategy

Scale to ~942x550 for fast reading while preserving detail.

**2a. Overview (1 fps, full duration)**

Overall flow, pose transitions, BG stability.

```bash
ffmpeg -y -i <video> -vf "fps=1,scale=942:550" <out_dir>/overview_%02d.png
```

**2b. Critical-motion window (8 fps, ~1s window)**

Zoom into the moment that matters most — a dialogue beat, gesture, or expression change. Center the window on the scripted action timestamp.

```bash
# Example: action at t=1.0s, sample 0.7s-1.7s
ffmpeg -y -ss 0.7 -i <video> -t 1.0 -vf "fps=8,scale=942:550" <out_dir>/detail_%02d.png
```

For shots with no dialogue, use the critical gesture window (eye movement, head turn, hand action).

**2c. End-stage stability (4 fps, last ~2.5s)**

AI video models often degrade in the final seconds — morphing, finger drift, face collapse.

```bash
# For 10s video: sample 7.5s-10s
ffmpeg -y -ss 7.5 -i <video> -t 2.5 -vf "fps=4,scale=942:550" <out_dir>/end_%02d.png
```

Adjust timestamps proportionally for non-10s shots.

### 3. Read frames

Read all extracted frames in parallel (single message, many Read tool calls). Also read reference start/end frames if available. Preserve temporal order.

### 4. Score — 5 dimensions, 55 points

| Dimension | Weight | Max | What to look for |
|---|---|---|---|
| **Face consistency** | x3 | 15 | Identity stability. Same eyes, nose, hair, blush. Penalize: morph, identity drift, eye shape change, jaw migration. |
| **Micro-expression fidelity** | x3 | 15 | Does performance match the prompt's emotional intent? Penalize: model softening, wrong valence, missed beats, generic "pleasant" default. |
| **Drift / morph control** | x2 | 10 | Structural integrity of hands, fingers, props, clothing. Penalize: extra fingers, hand warping, prop morphing, button migration. |
| **Full-duration stability** | x2 | 10 | Does the shot hold together for the full duration? Penalize: late-stage collapse, accumulating drift, motion that starts fine then derails. |
| **Color / style match** | x1 | 5 | Target style preserved. Penalize: style drift (e.g. 2D to 3D), photorealism creep, color grading mismatch, oversaturation. |

Each dimension: provide 1-2 concrete frame-specific callouts (e.g. "end_07: left index finger merging with middle finger").

### 5. Decision matrix

| Score | Verdict | Action |
|---|---|---|
| >= 45 | **Golden** | Lock model + seed. Ship it. |
| 40-44 | **Viable** | Ship, but consider one comparison with a stronger model for critical shots. |
| 30-39 | **Marginal** | Re-roll with tightened prompt, or A/B test a different model. |
| < 30 | **Fail** | Do not use. Switch model, split shot, or rework prompt/references. |

### 6. Report format

```markdown
# <Model> Scorecard — <ShotID>

## TL;DR
<2-3 sentence verdict with score and the single most important finding>

## Frame-by-frame observations
### Overview (0-Ns)
<table: timestamp | observation>

### Critical motion window
<did the scripted action happen? pass/fail with frame references>

### End stage
<late-stage stability verdict>

## Scorecard
| Dimension | Weight | Raw | Weighted | Notes |
|---|---|---|---|---|
| Face consistency | x3 | X/15 | X | ... |
| Micro-expression | x3 | X/15 | X | ... |
| Drift / morph | x2 | X/10 | X | ... |
| Stability | x2 | X/10 | X | ... |
| Style | x1 | X/5 | X | ... |
| **Total** | | | **X/55** | |

## Critical notes
<actionable issues: missing props, BG mismatch, lip sync needed, seed to preserve>

## Next moves
<ship / re-roll / switch model / A/B test>
```

## Tips

- **Score the model against the brief**, not the brief itself. If reference frames have a BG mismatch, that is a brief problem — flag it but don't penalize the model.
- **Props missing from output** that aren't in reference frames: the model cannot create what it wasn't shown. Score the prompt/reference setup.
- **Mouth never moves for scripted dialogue**: expected for models without native audio. Note that lip-sync post will be needed, but don't penalize drift.
- **Mouth moves continuously when it should be still**: this IS a model failure ("liveliness bias"). Penalize under Micro-expression.
- **Read 20+ frames in parallel**: single message with many Read calls. Never one at a time.
- **Scoring calibration**: 55/55 is near-impossible. 45-50 is excellent. Most first-run outputs land 35-42.
- **The scorecard is advisory**: the user's eye is the final judge. Present numbers with reasoning so they can override.
