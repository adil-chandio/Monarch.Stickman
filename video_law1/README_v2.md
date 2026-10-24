# 🎬 MonarchVoice — LAW 1 · v2 CINEMATIC (9:16)

Hook-first, sound-designed, camera-driven cut of **The 48 Laws of Power — Law 1: Never Outshine the Master**.

**Final video:** `v2out/MonarchVoice_Law1_v2_CINEMATIC_9x16.mp4`
**Specs:** 1080 × 1920 (9:16) · **72.6 s** · 30 fps · H.264 (CRF 18) + AAC 224 kbps · **−14 LUFS / −1 dBTP**

---

## 🆚 v1 vs v2 — kya upgrade hua

| | v1 (pehla cut) | **v2 (cinematic)** |
|---|---|---|
| Script | straight explainer, 66 s | **hook → cliffhanger**, 73 s ("RUK JAO!", "…warna") |
| Camera | static frames | **Ken Burns push/pull + camera shake** on hits, per-beat moves |
| Captions | word reveal | **kinetic**: pop-in, newest word punch-scale, gold highlight plates, shine sweep |
| Transitions | hard cut | **slide / wipe / slam / iris / flash / punch** (screen-space) |
| Particles | none | dust, **embers (fire scene)**, confetti (credit scene), sparks |
| Post FX | flat | **film grain, vignette, colour grade per beat** (warm palace → cold jail → night end card) |
| Sound | voice + soft pad | **full score + 14 procedural SFX types**, sidechain ducking, compression, −14 LUFS master |
| Branding | static | progress bar, LAW 01/48 tick marks, animated end-card CTA + swipe cue |

---

## 🎙️ Narration (Urdnglish) & beats

| # | Time | Narration | Visual treatment |
|---|------|-----------|------------------|
| 1 | 0:00 | **Ruk jao!** Agar aap apne boss se zyada smart hain, to yeh video aapki job bacha sakti hai. | red "RUK JAO!" slam, warning icon with shock rings, mascot |
| 2 | 0:07 | 48 Laws of Power. Law No. 1: **never outshine the master.** | crown descends, LAW ONE kinetic type, gold divider |
| 3 | 0:13 | 1661, France. Nicolas Fouquet … ek aisa palace banwaya… | spotlight, king card, typewriter name |
| 4 | 0:22 | …ke har mehman kehta: "Yeh to king se bhi zyada royal hai!" | framed palace still (push-in), speech bubble |
| 5 | 0:27 | King muskuraya. Tareef ki. Lekin andar… **jalan** ne aag pakad li. | growing flame, embers, heat vignette |
| 6 | 0:33 | Aur kuch hafton baad? Fouquet **giraftar**. Baaki zindagi jail mein. | bars slam down, white flash, GIRAFTAR! stamp, chains SFX, heartbeat |
| 7 | 0:42 | Law No. 1 ka matlab: master ko kabhi **insecure** mat karo… | spotlight on MASTER, crown, side callout |
| 8 | 0:50 | Talent dikhao, lekin **credit master ko do**… | scales tilt, TALENT⚖️CREDIT, confetti, coin SFX, jumping mascot |
| 9 | 0:57 | Log kamyabi bhool jate hain… lekin **beizzati**? kabhi nahi bhoolte. | quote card + ticking clock, underline |
| 10 | 1:03 | Yeh thi Law One. Agli law? Woh aur zyada **khatarnak** hai. Follow karo… warna. | dark chained-hand end card, embers, glitch, CTA shine, swipe cue |

---

## 🔊 Sound design (all synthesized, zero stock samples)

**Music** — 84 BPM, Am–G–F–C progression, key-tracked per bar:
- pad (3-voice detuned, brightness follows section energy)
- sub-bass on 1 & 3, kick 4-on-floor at high energy, hats 8ths, snare on 3
- 8th-note pluck arp with stereo ping-pong
- builds: risers + booms into beats 2, 6, 10

**SFX library** (procedural DSP in `audio_v2.py`):
`whoosh` (swept band-pass) · `boom` (sub drop + thump + crack) · `riser` · `clang` (inharmonic partials) · `chains` (randomised clanks) · `fire` (crackle + noise bed) · `heartbeat` · `ding` (bell partials) · `coin` · `tick` · `pop` (cue ticks) · `impact` · `glitch` · `reverb` (convolution IR)

**Mix:** voice −1.6 dBFS peak → 2.4:1 compression → **sidechain ducking** (music −60 %, SFX −30 % under voice) → bus compression → soft limiter → loudnorm −14 LUFS / −1.0 dBTP.

---

## 🛠️ Files

```
video_law1/
├── timeline_v2.py     # beats + cues + auto cue timing (edit this for a new topic)
├── audio_v2.py        # music + SFX synthesis + voice mix  → v2out/mix_v2.wav
├── vlib.py            # drawing, camera, particles, transitions, post-FX library
├── render_v2.py       # 10 scenes + kinetic captions + composition → MP4
├── audio_v2/beat01..10.mp3
├── assets/  fonts/
└── v2out/             # final MP4, QA stills
```

Rebuild:

```bash
cd video_law1
/tmp/v/bin/python render_v2.py timeline          # timings
/tmp/v/bin/python render_v2.py stills 12 30 45   # spot frames
/tmp/v/bin/python render_v2.py full              # render + score + mux (~7 min)
```

**Naya topic:** `timeline_v2.py` ke `BEATS` badlo (cues + gold keywords), nayi `audio_v2/beatNN.mp3` daalo, `render_v2.py` ke `sN()` scenes tweak karo, aur `full` chala do. Camera/grade/particles per beat `CAM`, `GRADE`, `PARTS` dicts se control hote hain.
