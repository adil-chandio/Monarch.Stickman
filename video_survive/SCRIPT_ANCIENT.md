# "How Ancient Humans Survived" — 46 s, 9:16, easy Urdnglish

Format: short-form story reel. Story carried by kinetic on-screen text + narration
(voice is a drop-in slot, see the end). Every timing below is what the picture and
the sound design are cut to.

| # | in | out | line (on screen / narration) | visual |
|---|---|---|---|---|
| 1 | 0.30 | 4.60 | **20,000 SAAL PEHLE** — na ghar, na kapde, na khana | cave mouth, cold blue night, a lone silhouette |
| 2 | 4.60 | 9.20 | Har subah ek hi sawal: **aaj zinda rahoge ya nahi?** | predator eyes in the dark, silhouette turns |
| 3 | 9.20 | 14.30 | Phir insaan ne **aag** ko dost banaya | lightning strike → fire ignites, embers |
| 4 | 14.30 | 18.60 | Aag = **garmi**, **roshni**, aur darinde **door** | fire circle, three figures, warm light |
| 5 | 18.60 | 23.10 | Pathar tod ke **hathiyar** banaye | stone knapping, spearhead, sparks |
| 6 | 23.10 | 27.80 | Akele **kamzor**. Jhund mein **khatarnaak** | mammoth silhouette; group of hunters with spears |
| 7 | 27.80 | 32.20 | Janwar ki khaal = **jacket**. Gufa = **ghar** | hide cloak, cave interior, sleeping family |
| 8 | 32.20 | 36.70 | Sabse bada hathiyaar? **Zubaan** | two figures talking, sound-wave rings, story around fire |
| 9 | 36.70 | 41.20 | Phir beej boya… **khana khud ugaya** | seeds → sprout → wheat field, sunrise |
| 10 | 41.20 | 46.00 | Hum wahi insaan hain. Sirf **tools** badle hain | modern phone glow in hand, city night |

Word budget: ~115 words ≈ 46 s at story-telling pace (~2.5 w/s).
Narration would sit at −21 dBFS RMS, score 8 dB under it, accents ≤ −9 dBFS peak.

## Voice-over slot

The picture is locked to the table above. To add narration, drop **one file per
beat** into `audio_sh/` (`beat01.wav` … `beat10.wav`, 48 kHz, mono or stereo).
`tighten_sh.py` trims each file to speech and re-fits it to the beat slot exactly
like `tighten.py` does for the Law videos, then `audio_sh.py` mixes it in.

Without those files the video is delivered as **picture + full sound design**
(score + accents), which already carries the story through the on-screen text.
