# Document skeletons

Adapt these freely. Drop sections that would be empty and rename headings to fit the content.
`[t]` means a `[HH:MM:SS]` reference into the video.

---

## Meeting minutes

```
# <Meeting purpose> - <date if known>
**Source:** ... · **Duration:** ... · **Attendees:** A, B, C (D joined at [t])

## Summary
<What the meeting was for, what was decided, what happens next. 5-8 sentences.>

## Decisions
| # | Decision | Rationale | Decided by | [t] |
|---|---|---|---|---|

## Action items
| Owner | Action | Due | [t] |
|---|---|---|---|

## Discussion
### 1. <Topic> [t]
<Context → points raised (attributed) → outcome.>
![...](frames/F00x_...jpg)
*Fig 1 - <what to look at>. [t]*

### 2. <Topic> [t]
...

## Open questions / parking lot
- <question> - raised by X [t]

## Appendix: Timeline index
| Time | Topic |
|---|---|
```

---

## Presentation / lecture / webinar notes

```
# <Talk title from the title slide>
**Speaker:** ... · **Source:** ... · **Duration:** ...

## Summary
## Key takeaways
1. ...

## <Section that follows the talk's structure> [t]
<Prose + bullets. The slide's important content goes into the text; add the screenshot when it has a visual.>
![...](frames/...)
*Fig n - ... [t]*

## Q&A
**Q (<asker if known>):** ... [t]
**A:** ...

## Resources mentioned
- <links, papers, tools named in the talk>

## Appendix: Timeline index
```

---

## Tutorial / demo / how-to guide

```
# How to <goal>
**Source:** ... · **Duration:** ... · **Tools/versions shown:** ...

## Overview
<What you'll end up with, who it's for.>

## Prerequisites
- ...

## Steps
### Step 1 - <action> [t]
<Exact instruction: menu path, button label, command.>
```bash
<command exactly as shown on screen>
```
![...](frames/...)
*Fig 1 - <the state you should see after this step>. [t]*

### Step 2 - ...

## Verifying it worked
## Troubleshooting / gotchas mentioned
## Appendix: Timeline index
```

Tutorial rule: every step that changes what's on screen gets a screenshot of the
**result** of that step. Copy commands and code from the screen exactly, not from the speech.

---

## Interview / podcast / panel

```
# <Topic> - conversation with <guest>
## Summary
## Key themes
### <Theme> [t]
<Synthesis across the conversation, with short quotes.>
> "<exact quote>" - Name [t]
## Notable Q&A
## Mentions (people, books, products, links)
```

---

## Design / architecture review

```
# <System / proposal name> - design review
## Summary
## Context & problem [t]
## Proposal [t]
<Diagram screenshot(s), with each component explained in text.>
## Alternatives considered
| Option | Pros | Cons | Verdict |
## Concerns & feedback
- <concern> - raised by X; response: ... [t]
## Decisions & next steps
## Appendix: Timeline index
```
