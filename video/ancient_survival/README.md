# Ancient Survival — 30-second Easy Urdunglish Reel

[Watch the finished 1080 × 1920 MP4](../Ancient_Survival_Easy_Urdunglish_30s_Reel.mp4).

A portrait-format illustrated explainer about **how prehistoric people survived**, built as a real character-animation piece rather than a slideshow of painted scenes. The backgrounds are empty illustration plates; the cast is a separate pose rig that the renderer walks, bends, kneels, leans and lights in every shot. It uses a user-selected narrator plus an original procedural music-and-foley mix. **No footage or audio from the fire reference clip is reused.** The running caveperson in the opening is this repository's earlier original wheel-cartoon sprite.

## Character animation system

| Element | File | How it moves on screen |
| --- | --- | --- |
| Empty plates | `assets/bg_clearing.png`, `bg_camp.png`, `bg_path.png`, `bg_mudbank.png`, `bg_night.png` | Cut-in camera punch that decays, Ken-Burns push/pan, handheld sway and graded warm/cool lighting; no baked-in characters |
| Walk cycles | `assets/walk_lookout.png`, `walk_woman.png`, `walk_elder.png` (contact, passing, contact, passing) | True four-pose cycles with a foot-plant bob, so steps alternate instead of swapping two stills |
| Lookout rig | `assets/sheet_lookout.png` (stand, walk A, walk B, knapping) | Scanning stance, one confident step, strike recoil and knapping sparks |
| Berry-picker rig | `assets/sheet_woman.png` + `sheet_pick.png` | Loop of reach-high / reach-low picking with body sway and falling berries |
| Elder rig | `assets/sheet_elder.png` | Walk cycle while crossing with firewood, kneeling hand-warming with hand rub |
| Campfire rig | `assets/sheet_lookout_sit.png`, `sheet_woman_sit.png` | Seated lookout poking the fire, woman turning food on a stick, both in a slow idle |
| Running hook | `../assets/caveperson_run.png` | Bolting character with speed dust, motion streaks and a camera-side entry |

`sprites.py` slices each sheet into equal cells, keys the white background to transparency (with a density pass that drops stray specks from neighbouring cells), **re-centres every pose on the support-foot anchor** so the character cannot slide sideways between frames, and scales the poses of a sheet by one shared factor so a character never "breathes" in size. Pastes are anchored on the feet baseline. Night scenes re-tint the same rig instead of using separate art.

## 2.5D multiplane depth

The renderer is a **2.5D multiplane camera**, the classic animation-camera technique: flat illustration planes stacked in depth, each moving by a different amount as the camera dollies.

| Plane | Parallax | Treatment |
| --- | --- | --- |
| Background illustration | 1.0 | Cut-in punch, push/pan, graded |
| Character sprites | 1.0 (stage space) | Four-pose walk cycles, foot-plant dust, contact shadows |
| Near foliage (`assets/fg_grass.png`, `fg_bush.png`) | 1.35–1.55 | Oversized, softly defocused, darkened, drifts hardest with the camera |
| Extreme-close silhouette | 2.4 | Heavy blur, deep shadow, clips one bottom corner for a shot-through-bushes feel |
| Dust motes | 0.35–1.0 | Warm (day) or cool (night) lit particles drifting through the near plane |

This gives real depth without a 3D renderer. A triangle-mesh/3D pipeline needs Blender or a GPU stack, which this sandbox does not have; the multiplane rig provides the parallax, focus falloff and camera-move feel those shots would use, and stays fully reproducible with Pillow + NumPy.

## Motion, type and sound design

- **Kinetic captions:** each line slides in from opposite sides with a small overshoot, scales on its own offset, settles, then lifts away with a gold highlighter swipe underneath.
- **Camera:** a six-frame punch-in and decaying shake on every cut, plus a slow push/pan for the whole shot.
- **Atmosphere:** warm/cool grade, animated film grain, dust kicks on foot plants, volumetric firelight rays, embers, speed streaks and a hand-drawn flame.
- **Sound:** original D-minor score with percussion and shaker, wide wind bed, forest chirps, stone chips, fire pops, footsteps timed to each walk cycle's contact frames, transition whooshes, risers into the two big reveals and sub impacts on every cut. Music is ducked under the narration and mastered to −13 LUFS with a −1.5 dBTP ceiling.

## Story and factual framing

Narration (Easy Urdunglish):

> Raat ka jungle. Na phone, na safe ghar. Socho, ancient log survive kaise karte the? Jawab: teamwork. Ek pehra deta, doosra berries aur roots dhoondta. Sharp pathar se tools bante, mil kar shikar hota. Aag se garmahat, roshni aur paka hua khana milta. Aur nahi, sab log hamesha caves mein nahi rehte the; camps bhi badalte the. Unki asli superpower strength nahi, planning aur ek doosre ka saath tha.

This is a **fictional composite explainer**, not a claim that one particular person/group invented fire, hunted the same way everywhere, or lived in one exact historical era. Food gathering, stone tools, fire and mobile shelters varied by place and time; the reel highlights cooperation as a broad survival theme. The opening is a dramatic question, not a claim that ancient people had no shelters.

## Re-render / edit

```bash
python3 -m pip install -r video/ancient_survival/requirements.txt
python3 video/ancient_survival/render_reel.py
# Optional single-frame art-direction preview:
python3 video/ancient_survival/render_reel.py --frame-at 16 --frame-output /tmp/fire.png
```

`render_reel.py` creates exactly 720 frames at 24 fps (30.00 s), with portrait 1080 × 1920 H.264 video and a 48 kHz stereo AAC track. `compose_audio.py` synthesizes the original D-minor score, percussion, wind, footsteps, stone chips, crackling fire and transition whooshes, ducks the music under `narration.wav`, and masters the mix to a safe peak. Temporary render files stay in `_build/` and are ignored by Git.

Captions are timed to the actual pauses in the approved narrator's WAV; shot framing, walk phase, character placement, fire timing and caption copy all live in `render_reel.py`, and the rig helpers live in `sprites.py`. Camera framing is deliberately chosen so that every character's feet stay above the caption band (`CAPTION_Y`).

## Font credit

Barlow Condensed Black and Bold are from [The Barlow Project / Google Fonts](https://github.com/google/fonts/tree/main/ofl/barlowcondensed), licensed under the SIL Open Font License 1.1. The full license is included at [`fonts/OFL.txt`](fonts/OFL.txt).
