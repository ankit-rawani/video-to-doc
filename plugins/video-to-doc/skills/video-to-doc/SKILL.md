---
name: video-to-doc
description: Turn a long-form video (meeting recording, lecture, demo, tutorial, webinar, walkthrough, interview, screen recording) into a well-structured document with screenshots taken from the video placed where they clarify the text. Use when the user gives a video file (.mp4, .mkv, .mov, .webm, .avi, ...) and asks for notes, minutes, a write-up, documentation, a summary document, a guide/SOP, or "a doc from this video".
argument-hint: <path-to-video> [--transcript file.vtt] [--format md|docx] [extra instructions]
allowed-tools: Bash(python *) PowerShell(python *) Read Write Edit Glob
---

# Video → Document

Make a document a reader can use **instead of watching the video**. Its structure follows the
video's content, and every visual moment that matters (slides, diagrams, UI steps, code,
whiteboards, charts, demos) shows up as a screenshot next to the text it explains.

Scripts live in `${CLAUDE_SKILL_DIR}/scripts/`. Run them with `python`. If `${CLAUDE_SKILL_DIR}`
isn't set (e.g. in the Claude app), use the folder that contains this SKILL.md.

## Step 0: Inputs

From `$ARGUMENTS` / the conversation, work out:
- **Video path** (required). If it's missing, ask for it.
- **Existing transcript.** Teams/Zoom/Meet/YouTube often provide a `.vtt`/`.srt`. Look next to the
  video for a file with the same name, or one the user names. Prefer it to Whisper: it's faster
  and it **keeps speaker names**.
- **Output format.** Default is Markdown plus a `.docx` with embedded images. Do only Markdown
  if the user asks for that.
- **Audience or focus** the user mentioned (e.g. "for the eng team", "just the decisions").

Dependencies: `opencv-python`, `numpy`, `faster-whisper` (only needed when there's no transcript
file), `python-docx`, `pillow`. If an import fails, run
`python -m pip install opencv-python faster-whisper python-docx pillow`. No separate ffmpeg is needed.

## Step 1: Extract (one command)

```
python "${CLAUDE_SKILL_DIR}/scripts/extract.py" "<video>" [--transcript "<file.vtt>"]
```

This is slow on long videos: roughly 0.1-0.3× real time for Whisper `small` on CPU, plus a frame
pass. **Run it in the background** and wait for the completion notification; don't poll it.
Re-runs reuse finished stages. `--only frames|transcript|timeline` redoes one stage, and
`--force` redoes everything.

Useful flags: `--model base` (faster, rougher) / `medium` (slower, better), `--language en`,
`--device cuda`, `--threshold 0.03` (fewer frames) / `0.008` (more frames),
`--max-gap 60` (force a frame at least every N s).

It writes a workspace `<video_stem>_vdo2doc/` next to the video containing:

| File | What it is |
|---|---|
| `meta.json` | duration, resolution, counts, list of parts and sheets |
| `transcript.json` | `[{start, end, text, speaker}]` |
| `frames/F###_HH-MM-SS.jpg` | one frame per visually distinct screen, taken once it has settled (slide build-ups captured complete) |
| `frames.json` | `[{id, file, start, end, revisit}]`. `revisit` = the screen came back later |
| `contact_sheets/sheet_##.jpg` | grids of 20 thumbnails labelled `F### start-end` |
| `parts/part_##.md` | 15-minute chunks of the merged timeline |
| `timeline.md` | all parts in one file |

Timeline lines look like:
```
[00:12:30] >>> SCREEN F012: frames/F012_00-12-30.jpg (on screen until 00:14:02)
[00:12:31] Priya: So the new ingestion path goes through the queue first...
```

If the frame count looks wrong for the content (e.g. 400 frames for a talking-head call, or
3 frames for a slide deck), rerun with `--only frames` and a different `--threshold`.

## Step 2: Understand the video

1. Read `meta.json`.
2. **Look at every contact sheet** with the Read tool. This shows you what was on screen across
   the whole video in a few images. Note which frames are content (slides, screens, diagrams,
   code, whiteboard, demo) and which are filler (webcam grids, black, loading screens, transitions).
3. **Read the whole timeline**, part by part. For each part, write down in your working notes
   (not a file): topics and where they start or change, key points, decisions, action items,
   numbers, names, questions, and **which frame IDs back up which points**.
   - Videos over about 90 minutes: read the parts in order and keep a running outline. If
     context gets tight, give each part to a subagent with the instructions in
     `reference/part-notes.md`. Have it return compact notes plus frame picks, then combine them.
4. **Open candidate frames at full size** with the Read tool before choosing them. Thumbnails
   hide detail. You need to see what the picture actually shows so the caption and nearby text
   describe it correctly. If a frame you need doesn't exist (e.g. a demo moment that was in
   motion), grab one:
   ```
   python "${CLAUDE_SKILL_DIR}/scripts/grab.py" --video "<video>" --at 00:41:07 -o "<ws>/frames/X01_00-41-07.jpg"
   ```
   To zoom in on part of a busy screen (a chart in a corner, one panel of a UI), crop it:
   ```
   python "${CLAUDE_SKILL_DIR}/scripts/grab.py" --image "<ws>/frames/F012_00-12-30.jpg" --crop 0.5,0.1,0.5,0.6 -o "<ws>/frames/F012_crop.jpg"
   ```

## Step 3: Pick the shape of the document

Choose the structure that suits the content. Read `reference/templates.md` for full skeletons.

| Video type | Signals | Document shape |
|---|---|---|
| Meeting / standup / review | several speakers, discussion, decisions | Minutes: summary, attendees, agenda topics → discussion → decisions, action items table, open questions |
| Presentation / lecture / webinar | one main speaker, slide deck | Structured notes: summary, sections that follow the talk's argument, key takeaways, Q&A |
| Tutorial / demo / how-to | UI or terminal, "click", "now we run" | Guide: prerequisites, numbered steps with a screenshot for each important step, troubleshooting, result |
| Interview / podcast / panel | Q&A rhythm, little on screen | Themes or Q&A digest with quotes; use few images (only real visuals) |
| Design review / architecture walkthrough | diagrams, whiteboard | Context, proposal with diagrams, alternatives, concerns raised, decisions |
| Mixed / other | | Executive summary + chronological sections by topic |

Combine shapes when the video mixes them (e.g. a meeting that contains a demo gets minutes
with a step-by-step demo section).

## Step 4: Write the document

Write `<ws>/<video_stem>.md`. Image paths are **relative to the workspace**
(`frames/F012_00-12-30.jpg`) so the Markdown renders and `build_doc.py` can find them.

### Content rules
- **Organise by topic, not by minute.** Merge points that recur at different times. Keep a
  `[HH:MM:SS]` reference at the start of each section (and on key claims) so readers can check
  the source.
- **Write it up; don't transcribe.** Clean, complete sentences. Keep the real substance:
  numbers, names, versions, commands, URLs, thresholds, dates, trade-offs, and the *reasons*
  behind decisions. Use short direct quotes only where the exact wording matters.
- **Attribute** opinions, decisions and action items to speakers when names are known. If the
  transcript has no speaker labels, don't make names up. Use names people say aloud
  ("thanks, Raj") only when it's clear who they refer to; otherwise write "a participant".
- **Action items**: owner, task, due date if one was said. Mark inferred owners "(inferred)".
- **Fix transcription errors** using context and the screenshots. Slide text is the best source
  for spelling product names, acronyms and figures. If something is still unclear, write
  `[unclear]` rather than guessing.
- Include nothing that isn't in the video. Put any helpful context of your own in a clearly
  labelled note.

### Screenshot rules
- **Add a screenshot wherever text alone would be ambiguous or much weaker**: slides with
  diagrams, charts or tables; architecture drawings; UI states in a tutorial (one per important
  step); code or terminal output; whiteboards; before/after comparisons; anything the speaker
  points at ("as you can see here", "this one", "over there"). Words like these in the
  transcript are a strong sign a screenshot is needed.
- **Leave out** webcam grids, faces, black or transition frames, duplicate screens, and
  slides that are only a title or a few bullets (put those bullets in the text instead).
- **Put each image right after the paragraph it supports.** Give it a caption that says what
  to look at, not just what it is:
  ```
  ![Fig 3 - Proposed ingestion pipeline: events now pass through the queue before the writer](frames/F012_00-12-30.jpg)
  *Fig 3 - Proposed ingestion pipeline: events now pass through the queue before the writer. [00:12:30]*
  ```
  (The italic line under the image is the visible caption. `build_doc.py` uses it as the DOCX
  caption.)
- If a slide contains dense text or data, **also put the important content in the text or a table**.
  Screenshots support the words; they don't replace them, and text stays searchable.
- Number figures in order. Aim for a useful number, not the largest: usually 1 every 2-5
  minutes of slide or screen content, and far fewer for discussion-only stretches.
- Crop with `grab.py --crop` when the relevant part is small within a busy frame.

### Front matter (always include)
```
# <Descriptive title taken from the content>
**Source:** <video file name> · **Duration:** HH:MM:SS · **Date:** <if known from content/filename> · **Participants/Speaker:** <if known>

## Summary
<5-10 sentence executive summary someone could read on its own>
```
Then the type-specific sections. End with an **Appendix: Timeline index**: a compact table
of `time | topic` that maps to the sections.

## Step 5: Build and check

1. Unless the user asked for Markdown only:
   `python "${CLAUDE_SKILL_DIR}/scripts/build_doc.py" "<ws>/<video_stem>.md"`
   It reports how many images it embedded. Exit code 1 means some image paths were wrong. Fix
   them and run it again.
2. Self-review before you report back:
   - Every image path exists and each caption matches what the image shows.
   - All decisions and action items in the timeline appear in the document.
   - No section is just a paraphrase of the transcript in time order.
   - Spelling of names and terms matches the slides.
3. Tell the user: where the `.md` and `.docx` are, the document's structure in one line, how
   many screenshots were used, and any caveats (rough audio, missing speaker names, `[unclear]`
   spots).

## Edge cases
- **No audio / silent screen recording**: use `--no-transcript`. Build the document from the
  frames alone: read each one and describe the steps or content.
- **No visuals worth showing** (audio only, talking heads): say so and produce a text document.
  Use at most one or two frames (e.g. a shared screen that appeared briefly).
- **Non-English**: Whisper auto-detects the language. Write the document in the language the
  user asks for (by default, the user's language) and keep the original terms where that helps.
- **Very long (3h+)**: suggest `--model base` to save time, use subagents per part, and include
  a table of contents.
- **URL instead of a file**: this skill needs a local file. Ask the user to download it, or
  use `yt-dlp` if it is installed and the user is OK with that.
