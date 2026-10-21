# Prompt pack

How to write the build prompt for a 3D film where real UI floats in space and
something (a cursor, a character, a hand) acts on it. The block layout, the
note format, the hit table and the sound prompt carry over to any look. The
glass, bloom and character settings below belong to one kind of inspo; take
yours from your own recipe.

The block structure is adapted from Clawd Motion Lab's "No After Effects"
prompt. The wording and the templates here are this skill's own.

## What makes this kind of film work

- **The UI is a web page.** Rebuild the screens in HTML with real labels and
  icons and screenshot them at 2-3x. The text stays sharp, and every element
  has a known pixel box.
- **Layout lives in one place.** timeline.py stores each control's rectangle
  in UI pixels. The HTML, the Blender scene and the sound script all read
  those numbers, so a press in 3D lands on the button in the texture and the
  click lands on the same frame.
- **Panels are separate slabs.** Cut the screenshot into one textured slab
  per panel so each can glow, dip, lift or fall on its own.
- **Results are drawn per frame.** Whatever the actor makes inside the app
  (a chart, a title, a cut) is a canvas drawn from the frame number, so it
  follows the app's real logic instead of a pasted video.
- **Glossy screens and big lights don't mix.** A glossy slab mirrors area
  lights as white rectangles. Keep rim and key lights out of glossy
  reflections (scene_kit has a helper).
- **Check before you spend GPU time.** A contact sheet of the 2D comp and
  about 18 half-size stills come before the full render.

## Prompt blocks

Only the first block changes from film to film. The others refer to its
names.

```
NAMES
ACTOR:   <who or what acts on the UI: shape, parts, size, exact hex colours>
APP:     <the product, panel by panel: name, state, real labels and layout>
RESULT:  <what the actor builds or changes, element by element>
SET:     <the space around it: background, floor, how the UI emits light>

FORMAT
Blender <version> Python, <EEVEE | Cycles> on GPU, <W>x<H>, <FPS> fps,
<seconds> s at <BPM> BPM. UI built in HTML and captured with puppeteer
at <scale>x. RESULT drawn on a canvas, one PNG per frame. src/timeline.py
holds the UI rectangles and every event; HTML, scene and sound read it.

BEATS
<t0>-<t1>  <the hook>
<t1>-<t2>  <how ACTOR enters the APP>
...        <each landing presses a real control and visibly changes RESULT>
<tN>-end   <the APP clears away; RESULT is left on screen>

CAMERA
<opening framing>, <how it follows ACTOR>, <how it reaches each target>,
<closing framing>.

LOOK
<from style-guide.md: materials, lighting, bloom, motion blur, view
transform, the colours that must read true>

CHECKS
Render the UI textures and a RESULT contact sheet first, then 18 stills at
half size, then the full film.
```

| Block | Why it's there |
|---|---|
| NAMES | The only part you swap. Everything else stays stable. |
| APP | Naming every panel and its state is what makes it read as the real product. |
| FORMAT | Fixes the tools and the single source of timing. |
| BEATS | Ties each action to a visible change. An action with no change gets cut. |
| LOOK | Comes from the recipe, with the settings that fixed problems in earlier previews. |
| CHECKS | Forces a look at cheap frames before the expensive render. |

## Writing follow-up notes

After each check, write what you saw and the change, with numbers, in the
order you saw it. A note without a number is a wish.

```
After the comp sheet
- the underline is too thin: 2 px -> 4 px
- the title clips the right edge at 4.2 s: move its end pose to x 190
- subtitle too small: 56 -> 78 px

After the stills
- key light shows as a white block on the glass: hide it from glossy rays,
  UI specular 0.1, roughness 0.32
- actor colour washes out: exposure 0.6 -> 0.15
- actor lands on top of the caption: land on the panel's right corner

After the full render
- actor leaves the frame at the top of the jump: apex 0.55 -> 0.36 m
- last frame is cut off on the right: land at x 800, not 862
- re-render only f105-f145 and f285-f360
```

## Hit table

Generate it from timeline.py, never by hand. Frame = time × FPS + 1. Each
press, landing and keyframe sits on a beat.

```
TIME          FRAME       PICTURE                          SOUND
0.00-1.50 s   f1-f46      wide on the app; hook            pad, light hats, the hook sound
2.00 s        f61         actor enters the app             impact, the beat starts
2.50 s        f76         first control pressed            click, UI blip
6.00-7.50 s   f181-f226   four presses, one per beat       rising notes
10.00 s       f301        the payoff                       stab, shimmer
11.20-12 s    f337-f360   RESULT alone                     chord rings out, fade
```

## Sound prompt

```
Synthesize the score and effects in Python (numpy, scipy). No samples, no
vocals. 48 kHz stereo WAV, <seconds> s. Read every event from timeline.py
and put each hit on its frame.

Music: <style from the inspo> at <BPM>, <chords>. Sparse before the hook
resolves; the full groove starts on <event>; a bigger chord on the payoff,
then let it ring and fade over the last 0.5 s.

Effects, one per event type: <press>, <landing>, <big move>, <reveal>,
<exit>. Same sound for the same event every time.

Master: compressor, then a limiter at -1 dBFS. Aim for -14 LUFS.
```

Check it with loudness per half second (sound.py writes reviews/sound.png).
The shape should follow the picture: quiet before the hook, a step up where
the groove starts, steady through the middle, a clear peak on the payoff, a
fall at the end. If one effect sticks out above the groove, turn it down.

## Rendering quickly

1. Build the UI capture and the RESULT frames.
2. Build the .blend: `blender -b --factory-startup -P src/scene.py`.
3. Render 18 stills at 50 % size and 40 samples; read them as one sheet.
4. Set the GPU device on every render call. It's a user preference in
   Blender, not saved in the .blend.
5. Encode H.264 High, CRF 17, the film's FPS, AAC 320k, `+faststart`.
