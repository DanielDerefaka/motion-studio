# Shot list: "Just Hide the HUD"

28 beats at 100 BPM, 18 frames a beat, 504 frames, 16.8 s. Frame = round(beat × 18) + 1.
Every number below is in `src/timeline.py`; the UI, the world comp, the Blender
scene and the sound all read it.

| Beats | Frames | Shot | Tobi | The world under him | Sound |
|---|---|---|---|---|---|
| 0–3 | 1–55 | Wide on the exploded game screen, pushing in to the sticker | A flat sticker on the market floor; two knocks, then it peels | Mile 1 Market, day | Muffled shaker; knock, knock, peel |
| 3–4 | 55–73 | Close on the sticker | Pops up into 3D; the glass over the world shatters | Market | Reverse swell, shatter, the beat drops |
| 4–8 | 73–145 | Low, close follow, f/2.8 | Four hops along the grown needs panel: Belle, Energy, Vibe, Water; each bar fills, mood goes Not happy → Okay → Very happy | Cuts on each landing: Jevinik, home, club, beach | Kick/clap groove; a ding per need (C E G C) |
| 8–12.3 | 145–222 | Low side angle | Drops onto the roof of the danfo as it drives in along the bottom, surfs it | Riding a danfo | Horn, engine, log-drum bass |
| 12.3–14 | 222–253 | Close | Off the bus onto the dock; kicks Spray money, ten ₦200 notes fly, cash drops 62,800 → 60,800 | Night hall | Clang, note flicks |
| 14–15 | 253–271 | Whip | Long front flip onto the Phone button; the phone rises | Night hall | Whoosh, click |
| 15–19 | 271–343 | Follow over the phone | Four hops on the real app tiles: Cars, Events, Property, Boutique | Ride drop-off, hall, estate, mall | Click per press, guitar |
| 19.5–21 | 352–379 | Pull back | Lands on Hide; every HUD panel powers down and tucks away, rippling out from Hide | The hall from above | Drums drop out; staggered power-down |
| 21–23 | 379–415 | Wide | Off the falling HUD onto the bare world, lands and dances | Hall, HUD hidden | Groove back, talking drum |
| 23–28 | 415–504 | Wide hold | Dancing beside the end card | Hall + end card | Shimmer; fade from beat 26.5 |

End card: the game's icon, "PH Lifestyle", "A free multiplayer life game in
Port Harcourt.", "phlifestyle.fun". The glass is the live place card's
computed style.

## 9:16

Its own camera (`CAMERA_9X16`), a tighter follow (0.4 against 0.22) so the
narrow frame keeps Tobi on the flip, and its own world texture
(`cache/screen-9x16/`) with the end card stacked and centred beside the dance.
