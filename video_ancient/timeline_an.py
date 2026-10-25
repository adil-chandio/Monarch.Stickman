#!/usr/bin/env python3
"""
timeline_an.py — 46 s beat map, cut in the *Law 1 style* (paper + host + captions).

Beat starts and durations are identical to `video_survive/timeline_sh.py`, so the
score, the 49 designed cues and the mastered mix all drop straight in.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

BEATS = [
    dict(n=1, kind="hook", trans="punch",
         start=0.30, dur=4.30,
         cues=[('20,000 SAAL PEHLE', ['20,000', 'SAAL', 'PEHLE']),
               ('na ghar, na kapde,', ['GHAR', 'KAPDE']),
               ('na khane ka bharosa.', ['KHANE'])],
         cue_ts=[0.10, 1.35, 2.75]),
    dict(n=2, kind="threat", trans="slam",
         start=4.60, dur=4.60,
         cues=[('Har subah...', []),
               ('ek hi sawal — zinda', ['ZINDA']),
               ('raho ge ya nahi?', ['NAHI'])],
         cue_ts=[0.10, 1.20, 2.55]),
    dict(n=3, kind="fire", trans="flash",
         start=9.20, dur=5.10,
         cues=[('Phir bijli ne AAG di.', ['BIJLI', 'AAG']),
               ('Aur insaan ne usko', ['insaan']),
               ('DOST bana liya.', ['DOST'])],
         cue_ts=[0.10, 1.70, 3.20]),
    dict(n=4, kind="warm", trans="slide",
         start=14.30, dur=4.30,
         cues=[('Aag = GARMI.', ['AAG', 'GARMI']),
               ('Aag = ROSHNI.', ['ROSHNI']),
               ('Aur darinde DOOR.', ['DOOR'])],
         cue_ts=[0.10, 1.25, 2.60]),
    dict(n=5, kind="tools", trans="whoosh",
         start=18.60, dur=4.50,
         cues=[('Pathar toda...', ['PATHAR']),
               ('...aur HATHIYAR bana.', ['HATHIYAR']),
               ('Shikaar aasan hua.', ['SHIKAAR'])],
         cue_ts=[0.10, 1.30, 3.00]),
    dict(n=6, kind="hunt", trans="slam",
         start=23.10, dur=4.70,
         cues=[('Akela insaan KAMZOR tha.', ['KAMZOR']),
               ('Magar JHUND mein...', ['JHUND']),
               ('...woh KHATARNAAK tha.', ['KHATARNAAK'])],
         cue_ts=[0.10, 1.40, 2.80]),
    dict(n=7, kind="shelter", trans="slide",
         start=27.80, dur=4.40,
         cues=[('Janwar ki KHAAL', ['KHAAL']),
               ('jaket ban gayi.', ['JAKET']),
               ('Gufa ghar ban gaya.', ['GUFA', 'GHAR'])],
         cue_ts=[0.10, 1.45, 2.70]),
    dict(n=8, kind="language", trans="whoosh",
         start=32.20, dur=4.50,
         cues=[('Aur sabse bada', ['SABSE']),
               ('hathiyaar? ZUBAAN.', ['HATHIYAAR', 'ZUBAAN']),
               ('Sikhana shuru hua.', ['SIKHANA'])],
         cue_ts=[0.10, 1.35, 3.10]),
    dict(n=9, kind="farm", trans="flash",
         start=36.70, dur=4.50,
         cues=[('Beej boya...', ['BEEJ']),
               ('...khana khud ugaya.', ['KHANA']),
               ('Bhookh kam hui.', ['BHOOKH'])],
         cue_ts=[0.10, 1.35, 3.05]),
    dict(n=10, kind="end", trans="punch",
         start=41.20, dur=4.80,
         cues=[('Hum wahi insaan hain.', ['INSAAN']),
               ('Sirf TOOLS badle hain.', ['TOOLS']),
               ('Follow karo — aage aur.', ['FOLLOW'])],
         cue_ts=[0.10, 1.35, 3.20]),
]

# --- voice-driven re-time -------------------------------------------------
# The narration is now the spine: a beat must be long enough to *finish* its line.
# Durations below come from the measured voice takes (trimmed) plus a short tail.
NEW_DUR = {1: 5.80, 4: 5.92, 6: 5.40, 7: 4.85}
_t = 0.30
for _b in BEATS:
    _old = float(_b["dur"])
    _new = float(NEW_DUR.get(_b["n"], _old))
    if abs(_new - _old) > 1e-6:            # captions spread across the new length
        _b["cue_ts"] = [round(c * _new / _old, 3) for c in _b["cue_ts"]]
    _b["dur"] = round(_new, 3)
    _b["start"] = round(_t, 3)
    _t = round(_t + _new, 3)

# cue_ts -> absolute times, the shape render_v3.draw_caption expects
for _b in BEATS:
    _b["cue_times"] = [dict(t=t, text=c[0], kw=c[1])
                       for t, c in zip(_b["cue_ts"], _b["cues"])]

TOTAL = round(BEATS[-1]["start"] + BEATS[-1]["dur"], 3)
