# Lessons from real runs

Each of these cost time on a real film (PH Lifestyle "Just Hide the HUD",
16.8 s, and the 30 s PH Lifestyle explainer; source in example/ph-lifestyle/).
Read before the step they belong to.

## Capture

- **Scope the hide CSS.** A child hidden inside a panel slab needs
  `html body <panel> <child>{visibility:hidden}`: unscoped, it loses to the
  `<panel> *{visible}` rule and the child stays printed in the parent's
  texture, so the separate child slab shows twice. (templates/capture/slabs.mjs does this.)
- **Snapshot the live DOM, don't rebuild it.** Clone it, strip scripts, add a
  `<base href>` to the live site: the product's own CSS, fonts and icons load
  as they are. Canvases don't clone; slabs.mjs swaps them for their last picture.
- **Record only as a guest or the studio's own account**, on a persistent
  profile, with the person logging in by hand (`snapshot.mjs --headed`). Never
  create accounts, bots or writes on a live product, and never type the person's credentials.
- **Wait for the product to be ready**, not for a fixed time: a selector,
  `document.fonts.ready`, then a settle. A first frame of a loading spinner
  ruins a clip.
- **Footage offsets run out.** A cut that starts 4.0 s into a 5 s clip and
  lasts 1.2 s freezes on its last frame. world.py lists every clip that ran
  out; fix the offset or record a longer clip; never accept the freeze.
- **A still page records nothing.** page.screencast only gets a frame when
  the page repaints, so a clip of a static page hung, then wrote a 0-byte
  webm ("EBML header parsing failed"). record.mjs injects a 1-px heartbeat
  that repaints every rAF and refuses an empty file.
- **A path the server sends as a download hangs the browser.** An
  extensionless file (`/pricing`) served as octet-stream never loads; record
  real routes, or serve `pricing/index.html` when testing locally.
- **Live numbers are what they were.** An online count, a price or a balance
  is whatever the product showed while recording. Never "improve" it.

## 3D (Blender)

- **Hide the lights from glossy rays.** Big area lights mirror in glossy UI
  slabs as white blocks. Set `visible_glossy = False` on key, rim and top
  lights; UI specular ≈ 0.1, roughness ≈ 0.32. The world slab can be the main
  light at night.
- **EEVEE first.** EEVEE ran at about 3.4 s a frame on Apple silicon (Metal),
  Cycles at 40–60 s a frame on a loaded machine. Shader compile after any
  scene change takes 2–5 min before the first frame: don't read that as a hang.
- **Exposure and the hero's colour.** Check the hero's hex in a still; on one
  film the hero read salmon until exposure dropped 0.6 → 0.15 and the base colour deepened.
- **The 9:16 camera is its own composition.** A tighter follow (0.4 vs 0.22),
  wider shots for panels, the end card stacked and centred. Never crop 16:9.
- **Keep the hero in frame on leaps.** Lower the apex (0.55 → 0.36 m on one
  film) or move the camera; check the frame at each apex in stills.
- **Anchors at the right height.** A callout anchored to an object's origin
  points at its feet; anchor to an empty at the part that matters.
- **Callouts whose anchor leaves the screen are hidden**, not clamped onto a
  wrong spot.

## 2D overlay

- **Fonts in a setContent page must be data: URIs.** file:// fonts don't load
  into `page.setContent`; embed them as base64.
- **This ffmpeg has no drawtext.** Draw all text in HTML or Blender; ffmpeg only composites and encodes.
- **Keep the transparent blank out of the frames folder.** A `_blank.png`
  next to NNNN.png broke the "all N frames" count in encode.

## Voice

- **Run the venv Pythons with `-I`.** A stray `bisect.py` in the working
  folder shadowed the stdlib `bisect` and broke the TTS import. Isolated mode
  keeps the cwd, user site-packages and PYTHON* env vars off the path; the
  scripts put src/ on the path themselves to import timeline.
- **Sample voices before choosing.** `voice.py --samples` writes one line in
  several voices; the person picks. af_heart at speed 1.1 was the explainer pick.
- **Measured line lengths drive the timeline.** VO entries hold beats; the
  real seconds come from cache/vo/<voice>/lines.json after voice.py runs, so
  rerun timeline.py after voice.py.

## Sound

- **Duck the bed under the voice by ~9 dB**, ~40 ms down, ~250 ms back, with
  lookahead; the fade touches only the bed. Deliver music.wav un-ducked too.
- **-14 LUFS integrated, ≤ -1 dBTP**, measured with the studio's own meter
  (sound.py prints it). Report the per-line voice-to-bed ratio; aim ≥ 10 dB broadband.

## Running long renders

- **Never pgrep for a string that appears in your own command line.**
  `pgrep -f "render.py -- 16x9"` matched the waiting shell itself and the wait
  never ended. Wait on the frame count (`ls out/frames-16x9 | wc -l`) or a PID.
- **Render the main format first and encode it before starting the next.**
  The person can review 16:9 while 9:16 renders, and a stop never leaves you
  with two half films.
- **render.py resumes**: frames already on disk are skipped. To fix a defect,
  delete only that frame range and re-render it (for example frames 105–145 and 285–360).
- **Encode refuses partial folders.** Count only `^[0-9]*\.png$`.
- **Report renders honestly**: frames done of total, seconds a frame, ETA.
  "Done" means the mp4 exists and ffprobe shows the right duration.

## Matching an inspo (the first non-PH proof, Sims 4 trailer, 2026-10-21)

- **Frame-step every signature move before writing its recipe line.** The
  whip was first written as "horizontal smear + lift" from one blurred frame;
  the step sheet showed a vertical push where the incoming shot rises with the
  outgoing one (its sky was the "gap"). Track the boundary per frame
  (5 / 20 / 55 % of H) and the curve falls out (ease-in quad).
- **Look at the compare sheet after every fix, not only the stills.** Round 1
  stills looked fine alone; beside the inspo the night was grey, not blue.
- **Check the title's weight and colour in a full-size frame.** A variable
  font registered for weight 400 only renders thin at 800 with no error
  (render2d.mjs now registers 1-1000), and a text role with no colour is black.
- **Read the footage for UI leftovers** (hint text, cursors at the edges)
  before choosing spans; crop with drawCover or pick another span.
