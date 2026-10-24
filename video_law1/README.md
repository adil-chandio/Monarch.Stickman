# 🎬 MonarchVoice — Law 1 Explainer (9:16 Vertical, Urdnglish)

Reference video jaisa hi **whiteboard-cartoon explainer** — naya topic: **The 48 Laws of Power — Law 1: Never Outshine the Master**.

**Audio research (v13 kit):** see `SOUND_KIT_RESEARCH.md` — real SoundFont instruments, `pedalboard` DSP, `matchering`/`pyloudnorm` mastering, convolution SFX design. Proof: `v3out/ab_reel.wav` (old bed → new bed) + `v3out/sfx_v13_demo.wav`.

**Latest final video (v12):** `v3out/MonarchVoice_Law1_v12_CINEMATIC_9x16.mp4` — 63.3 s, −14.7 LUFS, narration timing fixed (no doubled voice, no holes) + 3-layer dry bed 8 dB under the voice, see `README_v10.md`
**Earlier cuts:** v7/v8/v9 removed from the repo — each superseded (history only)
**Original v1 cut:** `out/MonarchVoice_Law1_Never_Outshine_The_Master_9x16.mp4`
**Specs:** 1080 × 1920 (9:16) · 65.7 sec · 30 fps · H.264 + AAC · −14 LUFS

---

## 🎯 Style Match (reference se copied)

| Element | Implementation |
|---|---|
| Whiteboard paper look | cream paper + grain + soft vignette |
| Blue caption bar (top) | `#1385E5`, rounded, drop shadow, drop-in pop per cue |
| Bold serif captions | Playfair Display Bold, word-by-word reveal, gold keyword highlight |
| Cartoon mascot | bald white head, blue shalwar kameez, thin ink outlines |
| Flat vector icons | warning / crown / flame / jail / scale, pop-in with ease-out-back |
| Photo insert | palace garden party framed like the reference "washed/shrouded" cards |
| Red accents | `#C41A2D` for danger words (WARNING, JALAN, GIRAFTAR, BEIZZATI) |
| Dark end card | cinematic chained-hand art + Urdnglish lines in white/gold serif |
| Branding | 👑 MONARCHVOICE (top-left) · LAW 01 / 48 (top-right) · progress line bottom |

---

## 🎙️ Timeline & Narration (Urdnglish)

| # | Time | Narration | Visual |
|---|------|-----------|--------|
| 1 | 0:00 | Agar aap apne boss se zyada smart hain... to yeh video aapke liye ek warning hai. | mascot + boss silhouette + warning icon |
| 2 | 0:06 | Law No. 1 — never outshine the master. Apne master ko kabhi neecha mat dikhao. | gold crown + LAW ONE typography |
| 3 | 0:15 | France, 1661. Nicolas Fouquet ne King Louis XIV ke liye ek aisa palace banwaya... | king on throne card |
| 4 | 0:22 | ...ke har mehman ne kaha: "Yeh to king se bhi zyada royal hai!" | Vaux-le-Vicomte party still + speech bubble |
| 5 | 0:28 | King ne muskura kar tareef ki... lekin andar hi andar jalan ne janam liya. | king + growing flame "JALAN" |
| 6 | 0:34 | Kuch hafton baad, Fouquet giraftar tha. Aur baaki saari zindagi jail mein. | iron bars + GIRAFTAR stamp |
| 7 | 0:40 | Law No. 1: apne master ko kabhi insecure mat karo. Usay lagta hai tumhari kamyabi uska inaam hai. | spotlight on MASTER + crown |
| 8 | 0:48 | Smart raho... lekin credit master ko do. Talent chhupana nahi — bas usay neecha mat dikhao. | talent ⚖️ credit + celebrating mascot |
| 9 | 0:55 | Kyunkay log kamyabi bhool jate hain... lekin apni beizzati kabhi nahi. | white quote card + red underline |
| 10 | 1:00 | Yeh thi Law One. Agli law mein milte hain, follow karna mat bhoolna. | dark chained-hand end card |

---

## 🛠️ Pipeline (kaise dobara banayein / naya topic)

```
video_law1/
├── timeline.py        # BEATS: narration cues + auto cue timing (single source of truth)
├── render.py          # PIL frame renderer → ffmpeg (scenes s1..s10, caption bar, overlay)
├── build_audio.py     # beat placement + soft music bed (Am–F–C–G pad) + loudness
├── audio/beat01..10.mp3  # TTS narration (Urdnglish voice)
├── assets/            # cartoon mascot + vector icons + reference-style art
├── fonts/             # Playfair Display + Inter (OFL)
└── out/               # final MP4
```

Rebuild everything:

```bash
cd video_law1
/tmp/venv/bin/python render.py full       # frames → silent MP4 → audio mix → final MP4
/tmp/venv/bin/python render.py stills 9.5 24 45   # spot-check frames only
/tmp/venv/bin/python render.py timeline   # beat timings
```

**Naya topic banane ke liye:**
1. `timeline.py` mein `BEATS` ke `cues` badal dein (har cue = ek caption bar line, with timings auto-derived from the narration length).
2. `audio/beatNN.mp3` nayi narration se replace karein.
3. `render.py` ke `sN()` scenes ko naye visuals/icons ke mutabiq tweak karein (assets folder mein naye icons daal dein).
4. `render.py full` chala dein.

Aspect ratio badalna ho to `W, H` (top of `render.py`) change karein — 16:9 ke liye `1920, 1080`, phir caption `CAP_W` aur scene y-positions adjust karne honge.

---

## 🎨 Palette

| Token | Hex | Use |
|---|---|---|
| Paper | `#FCFBF7` | background |
| Ink | `#1A1A1E` | outlines / headings |
| Caption blue | `#1385E5` | caption bar |
| Danger red | `#C41A2D` | warnings, stamps, highlight words |
| Gold | `#CB9E30` / `#FFD666` | crown, dividers, caption keywords |
