# Subagent brief: notes for one timeline part

Use this when a video is too long to read in one context. Give each subagent one
`parts/part_##.md` and the workspace path. Ask for the output below, **no more than ~600 words**.

---

You are summarising one part of a video transcript for a document writer. The workspace is
`<ws>`. Read `<ws>/parts/part_NN.md`. Lines starting with `>>> SCREEN` say which frame image
(`<ws>/frames/...`) was on screen from that time. Open with the Read tool any frame that looks
like real content (slide, diagram, UI, code, chart) so you know what it shows.

Return exactly:

```
PART NN (HH:MM:SS-HH:MM:SS)
TOPICS:
- [t] <topic>: <2-4 sentence synthesis, with concrete numbers/names/reasons>
DECISIONS:
- [t] <decision> - <who> - <why>
ACTION ITEMS:
- [t] <owner> - <action> - <due if said>
OPEN QUESTIONS:
- [t] <question> - <who raised it>
FRAMES WORTH INCLUDING:
- F0xx - <what it shows, in one line> - <which topic it supports>
FRAMES TO SKIP: F0xx, F0yy (webcam/duplicate/transition)
TERMS/SPELLINGS (from slides): <product names, acronyms, people>
CONTINUES INTO NEXT PART: <topic that is still in progress at the end, if any>
```

Don't make up speakers or facts. Write `[unclear]` where the audio is garbled.
