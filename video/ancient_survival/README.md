# Ancient Survival — 30-second Easy Urdunglish Reel

[Watch the finished 1080 × 1920 MP4](../Ancient_Survival_Easy_Urdunglish_30s_Reel.mp4).

A portrait-format illustrated explainer about **how prehistoric people survived**, built as a real character-animation piece rather than a slideshow of painted scenes. The backgrounds are empty illustration plates; the cast is a separate pose rig that the renderer walks, bends, kneels, leans and lights in every shot. It uses a user-selected narrator plus an original procedural music-and-foley mix. **No footage or audio from the fire reference clip is reused.** The running caveperson in the opening is this repository's earlier original wheel-cartoon sprite.

## Character animation system

| Element | File | How it moves on screen |
| --- | --- | --- |
| Empty plates | `assets/bg_clearing.png`, `bg_camp.png`, `bg_path.png`, `bg_mudbank.png`, `scene_night.png` | Camera push-in, pan, handheld sway and a slow Ken-Burns drift; no baked-in characters |
| Lookout rig | `assets/sheet_lookout.png` (stand, walk A, walk B, knapping) | Scanning stance, one confident step, alternating stride, strike recoil |
| Berry-picker rig | `assets/sheet_woman.png` + `sheet_pick.png` | Loop of reach-high / reach-low picking with body sway and falling berries |
| Elder rig | `assets/sheet_elder.png` | Walk cycle while crossing with firewood, kneeling hand-warming with hand rub |
| Campfire rig | `assets/sheet_lookout_sit.png`, `sheet_woman_sit.png` | Seated lookout poking the fire, woman turning food on a stick, both in a slow idle |
| Running hook | `../assets/caveperson_run.png` | Bolting character with speed dust and camera-side entry |

`sprites.py` slices each sheet into equal cells, keys the white background to transparency, trims the cell, and scales the poses of a sheet by **one shared factor** so a character never "breathes" in size between poses. Every paste is anchored on the feet baseline, which is what makes the generated two-pose walk cycles read as continuous motion. Night scenes re-tint the same rig instead of using separate art.

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
