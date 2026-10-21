# Method

A film here is a program. You write it, it draws every frame, ffmpeg encodes
the frames, and a review step decides if the result is good enough to show.
The idea of splitting the work into layers with gates between them came from
rari's "Motion Engineering" write-up (@0xwhrrari); what follows is how this
skill applies it.

## Five layers, five files

Each layer is a decision, and each decision is written to a file before the
next layer starts. When a decision is skipped, the safe default fills the
gap, and the safe defaults are exactly what make a film look like every other
demo: centred headline, gradient background, everything fading in, logo last.

| Layer | Decides | Lives in |
|---|---|---|
| Story | What the viewer should take away | brief.md |
| Look | How it should feel, measured from the inspo | inspo/analysis/, style-guide.md |
| Timing | What changes on each beat | shotlist.md, src/timeline.py |
| Render | How each frame is drawn | src/ |
| Review | What is wrong, at which frame, and the fix | reviews/ |

## Story: facts and choices

The brief keeps two lists apart.

- **Facts** come from the product: screens, numbers, names, prices, copy,
  logo. You use them as they are. If one is missing, stop and ask. Do not
  draw a believable stand-in.
- **Choices** are the film's: camera, pacing, the opening, which screen
  leads. You are free to make these up and change them.

templates/docs/brief.md has the fields: the one sentence, audience, length,
formats, the real assets with paths, what to keep from the inspo, what to
avoid, deliverables.

## Look: measure it

Pull frames, sample colours, count cuts (reference/inspo.md has the tools).
Write down values, not adjectives: hex codes instead of "premium", seconds
between changes instead of "fast", a cubic-bezier instead of "smooth". The
recipe covers palette, type, composition (where the eye lands first),
pacing, motion (snap, glide, overshoot, hard cut, hold) and texture (grain,
glass, paper, none).

The recipe says what to take. It also says what not to take: the inspo's
logos, people, copy, footage and music stay where they are.

## Timing: states, then beats

A list of effects isn't a plan. Start from what the viewer knows at each
moment. A short product film usually runs:

| Beat | Job |
|---|---|
| HOOK | One frame worth stopping for, in the first two seconds |
| PROBLEM | The friction, shown rather than explained |
| REVEAL | The product arrives through something real happening in it |
| PROOF | One screen or one number that backs the claim |
| CLOSE | A clean end state with a call to action you can read |

For UI, write the chain of states first (for example search → result →
detail → action → confirmed). A single component can grow, recolour, swap
its content and move while still reading as the same object.

Every row in shotlist.md has a purpose, an entry state and an exit state. If
nobody can say why a shot is there, it goes.

## Render: seekable, and as small as possible

Pick the lightest tool that can draw the look (pipeline.md lists the
branches). Whatever it is, frame N must come out of a pure function of N:

```
draw(frame, timeline, assets, style, seed) -> pixels
```

That rules out CSS animations, `setTimeout`, wall-clock time, physics that
has to warm up, and `Math.random()` without a seed. The test is simple:
render frame 240 on its own and compare it to frame 240 from a full run.

### Motion rules

One rule per kind of object, written in style-guide.md with numbers. For
example:

| Object | Rule |
|---|---|
| Small UI (toggles, chips, counters) | fast, almost no overshoot |
| Panels and cards | settle under control |
| Camera | slow, you shouldn't notice it |
| Headlines | land hard, then sit still |
| Characters | bouncy, but on purpose |

If every object bounces, none of them looks precise. After each move, the
viewer should know where to look next.

## Sound: same clock as the picture

Every cue is read from the same timeline.py events as the picture: the click
on the press, the cut on the beat, the resolve on the logo. Listen to the mix
with your eyes shut. If it has no shape on its own, it isn't done.

## Review: look at frames, not intentions

Before the full render, make a contact sheet: one frame per beat, plus short
strips around the fastest moves. Go through it with this list:

- [ ] Text is readable at phone size
- [ ] Nothing crosses the safe area
- [ ] Every product asset is real
- [ ] Type and colour stay consistent from scene to scene
- [ ] No ugly frames halfway through a transition
- [ ] Cuts and sound hits land together
- [ ] The first two seconds hook
- [ ] The last frame would work as a poster

After the rough cut, write `reviews/defects-<n>.md` with the three worst
problems you can see in the rendered frames. Each gets a timestamp (frame =
time × FPS + 1), what you saw, and a fix with numbers. Fix those three,
re-render only those frame ranges, and make a new sheet. A film is finished
when the sheets say so, not when the mp4 exists.

## Formats are separate compositions

16:9, 9:16 and 1:1 share the story, assets, timeline and states. Each gets
its own layout, line breaks and camera:

- 16:9 can show more space around the subject
- 9:16 needs fewer elements and a stronger top-to-bottom order
- 1:1 wants tighter type and shorter holds

Never crop one into another. Each format gets its own contact sheet.

## Studio layout

```
<film>/
  brief.md          the sentence, the audience, the product facts
  style-guide.md    the look recipe and motion rules
  shotlist.md       beats, states, times, purpose
  inspo/            copies of the references + analysis/
  assets/           real logos, screens, footage, fonts
  src/              timeline.py and the renderer
  reviews/          sheets, compare sheets, defect notes
  out/              films and posters
```

For the next film, swap the brief and the assets; the checklist, the gates
and the layout stay the same. Because the state is in files, a run can stop
at any point and resume from the last gate that passed.

## Gates

| Gate | What has to be true |
|---|---|
| 1 | Inspo and real product assets are in and approved |
| 2 | Look recipe and shot list approved |
| 3 | Representative stills pass the checklist |
| 4 | Rough cut rendered, contact sheet read |
| 5 | Three worst defects fixed |
| 6 | Sound, every format and the deliverables checked |

Between gates, work without asking. At a gate, show the evidence and wait.
Don't make brand calls the person hasn't made. When the inspo is unclear,
the next output is a question or a single test frame, not a full render in
the wrong direction.

## Production contract

Paste this at the start of a run, or keep it as the checklist the skill
follows:

```
Make a <N>-second film about <product> for <audience>.
The one thing to remember: <sentence>.

Use only the product's real assets and approved copy.
Measure the inspo and write style-guide.md before designing anything.
Write shotlist.md: times, purpose, entry and exit state per shot.

Pick a renderer and say why. Every frame seekable and deterministic.
Picture, text and sound all read one timeline. Keep the source and a
render command that rebuilds the film.

Stop and show: the recipe and shot list, then a contact sheet before the
full render. Score hook, readability, continuity, motion and sound sync.
Fix the three worst defects and re-render only those frames.
Build 16:9 and 9:16 as separate compositions.

Hand over the films, posters, contact sheets, source, the asset list and a
short note on what still needs a human eye.
```
