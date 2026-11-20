# video-to-doc

A Claude Code plugin that turns a long-form video into a document you can read **instead of watching
the video**. It works on meeting recordings, lectures, webinars, demos, tutorials, design reviews,
interviews and screen recordings.

Claude transcribes the audio, captures every distinct screen (slides, diagrams, code, UI steps,
whiteboards), reads it all, and writes a structured document. Screenshots are placed next to the
text they explain. You get Markdown, plus a Word (`.docx`) file with the images embedded.

The document's shape follows the content:

| Video | Document |
|---|---|
| Meeting / standup / review | Minutes: summary, topics, decisions, action items, open questions |
| Presentation / lecture | Structured notes following the talk, key takeaways, Q&A |
| Tutorial / demo | Step-by-step guide with a screenshot per step, troubleshooting |
| Design review | Context, proposal with diagrams, alternatives, concerns, decisions |
| Interview / podcast | Themes or Q&A digest with quotes |

See [`examples/falcon_review/falcon_review.md`](examples/falcon_review/falcon_review.md) for a sample output.

## Install

### 1. Prerequisites

- [Claude Code](https://docs.claude.com/en/docs/claude-code)
- Python 3.9+ on your `PATH` as `python`
- Python packages:

  ```
  python -m pip install opencv-python numpy faster-whisper python-docx pillow
  ```

  You don't need a separate ffmpeg install; audio is decoded with PyAV, which comes with
  `faster-whisper`. The first transcription downloads the Whisper model (~500 MB for `small`).

### 2. Add the marketplace and install the plugin

Inside Claude Code:

```
/plugin marketplace add <owner>/<repo>
/plugin install video-to-doc@vdo2doc
```

Or from a terminal:

```
claude plugin marketplace add <owner>/<repo>
claude plugin install video-to-doc@vdo2doc
```

Restart Claude Code so the skill is picked up. Check it with `/plugin` → *Installed*.

> For a private repo, your git credentials must have access, e.g. via `gh auth login`.
> You can also use the full URL: `/plugin marketplace add https://github.com/<owner>/<repo>.git`

### Install for a whole team (optional)

To have Claude Code offer the plugin automatically to everyone working in a project, commit this to
the project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "vdo2doc": {
      "source": { "source": "github", "repo": "<owner>/<repo>" }
    }
  },
  "enabledPlugins": {
    "video-to-doc@vdo2doc": true
  }
}
```

## Usage

Ask in plain language:

```
Make a document from "C:\recordings\design-review.mp4"
Turn ~/Downloads/standup.mp4 into meeting minutes, just the decisions and action items
```

Or invoke the skill directly:

```
/video-to-doc:video-to-doc "path/to/video.mp4"
/video-to-doc:video-to-doc "path/to/video.mp4" --transcript "path/to/video.vtt"
```

**Tip:** if you have a Teams / Zoom / Meet transcript (`.vtt` / `.srt`), put it next to the video
or point to it. It's faster than Whisper and keeps **speaker names**.

### Output

A workspace folder `<video name>_vdo2doc/` is created next to the video:

```
<video name>_vdo2doc/
├── <video name>.md      ← the document
├── <video name>.docx    ← same, with embedded images
├── frames/              ← extracted screenshots (referenced by the document)
├── contact_sheets/      ← thumbnail grids Claude uses to survey the video
├── transcript.json
├── timeline.md          ← transcript merged with screen changes
└── parts/               ← timeline in 15-minute chunks
```

### Timing

Extraction runs locally on CPU at about 0.1-0.3× real time with the Whisper `small` model. A
1-hour video takes ~10-20 minutes before Claude starts writing; Claude runs it in the background.
Tell Claude if you want a different speed/quality trade-off:

- *"use the base model"*: faster, rougher transcript
- *"use the medium model"*: slower, more accurate
- *"use CUDA"*: if you have an NVIDIA GPU

## Running the scripts yourself

The scripts live in `plugins/video-to-doc/skills/video-to-doc/scripts/` and can be run without Claude:

```
python extract.py "video.mp4" [--transcript video.vtt] [--model small] [--threshold 0.015]
python grab.py --video "video.mp4" --at 00:41:07 -o frame.jpg
python grab.py --image frame.jpg --crop 0.5,0.1,0.5,0.6 -o crop.jpg
python build_doc.py "<ws>/<video name>.md"
```

## Privacy

Everything runs locally: transcription, frame extraction and DOCX building. Nothing is uploaded
except what Claude reads while writing (the transcript and the screenshots it looks at).
Recordings often show credentials, keys or personal data on screen. **Review the screenshots
before sharing a generated document.**

## Updating / removing

```
/plugin marketplace update vdo2doc
/plugin uninstall video-to-doc@vdo2doc
```

## Repository layout

```
.claude-plugin/marketplace.json          marketplace catalog ("vdo2doc")
plugins/video-to-doc/
├── .claude-plugin/plugin.json           plugin manifest
└── skills/video-to-doc/
    ├── SKILL.md                         instructions Claude follows
    ├── scripts/                         extract.py, grab.py, build_doc.py
    └── reference/                       document templates, subagent brief
examples/                                sample output + synthetic test-video generator
requirements.txt
```
