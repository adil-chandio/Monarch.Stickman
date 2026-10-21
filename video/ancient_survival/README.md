# Ancient Survival — 30-second Easy Urdunglish Reel

[Watch the finished 1080 × 1920 MP4](../Ancient_Survival_Easy_Urdunglish_30s_Reel.mp4).

A new portrait-format illustrated explainer about **how prehistoric people survived**. It uses original generated storybook illustrations, an animated caveperson, moving camera, caption beats, fire/stone/forest effects, a user-selected narrator, and an original procedural music-and-foley mix. **No footage or audio from the fire reference clip is reused.** The caveperson sprite comes from this repository's earlier original wheel cartoon.

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

The visual scenes are in `assets/`. Captions are timed to the actual pauses in the approved narrator's WAV; all timing, shot motion, caption copy and fades can be adjusted in `render_reel.py`.

## Font credit

Barlow Condensed Black and Bold are from [The Barlow Project / Google Fonts](https://github.com/google/fonts/tree/main/ofl/barlowcondensed), licensed under the SIL Open Font License 1.1. The full license is included at [`fonts/OFL.txt`](fonts/OFL.txt).
