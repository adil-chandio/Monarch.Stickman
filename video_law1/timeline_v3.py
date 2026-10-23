#!/usr/bin/env python3
"""Timeline v3 — same narration, tuned for the premium sound design + visuals."""
import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(ROOT, "audio_v2")
FF = "/tmp/v/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"

LEAD = 0.30
GAP = 0.26
TAIL = 1.60

# cues: (text, keywords to highlight in gold)
BEATS = [
    dict(n=1, kind="hook", trans="punch", cues=[
        ("RUK JAO!", ["RUK", "JAO"]),
        ("Agar aap apne boss se", []),
        ("zyada SMART hain...", ["SMART"]),
        ("to yeh video aapki", []),
        ("JOB bacha sakti hai.", ["JOB"]),
    ]),
    dict(n=2, kind="title", trans="slide", cues=[
        ("The 48 Laws of Power", ["48", "POWER"]),
        ("LAW No. 1", ["LAW", "1"]),
        ("NEVER OUTSHINE", ["NEVER", "OUTSHINE"]),
        ("THE MASTER.", ["MASTER"]),
    ]),
    dict(n=3, kind="story", trans="whoosh", cues=[
        ("FRANCE \u00b7 1661", ["FRANCE", "1661"]),
        ("Nicolas Fouquet", ["Nicolas", "Fouquet"]),
        ("king ka finance minister", ["finance", "minister"]),
        ("ne ek aisa palace banwaya...", ["palace"]),
    ]),
    dict(n=4, kind="story", trans="whoosh", cues=[
        ("...ke har mehman kehta:", ["mehman"]),
        ("\u201cYeh to KING se bhi", ["KING"]),
        ("zyada ROYAL hai!\u201d", ["ROYAL"]),
    ]),
    dict(n=5, kind="danger", trans="flash", cues=[
        ("King muskuraya.", ["King"]),
        ("Tareef ki.", []),
        ("Lekin andar...", []),
        ("JALAN ne aag pakad li.", ["JALAN"]),
    ]),
    dict(n=6, kind="shock", trans="slam", cues=[
        ("Aur kuch hafton baad?", ["hafton"]),
        ("FOUQUET GIRAFTAR.", ["GIRAFTAR"]),
        ("Baaki zindagi JAIL mein.", ["JAIL"]),
        ("Sirf ek palace ki wajah se.", ["palace"]),
    ]),
    dict(n=7, kind="teach", trans="whoosh", cues=[
        ("Law No. 1 ka matlab:", ["Law"]),
        ("master ko kabhi", ["master"]),
        ("INSECURE mat karo.", ["INSECURE"]),
        ("Usay lagta hai tumhari kamyabi", ["kamyabi"]),
        ("uska inaam hai.", ["inaam"]),
    ]),
    dict(n=8, kind="bright", trans="slide", cues=[
        ("Talent dikhao...", ["Talent"]),
        ("lekin CREDIT master ko do.", ["CREDIT"]),
        ("Smart raho \u2014", ["Smart"]),
        ("magar uske saaye se bada mat bano.", ["saaye"]),
    ]),
    dict(n=9, kind="quote", trans="flash", cues=[
        ("Log KAMYABI bhool jate hain...", ["KAMYABI"]),
        ("lekin BEIZZATI?", ["BEIZZATI"]),
        ("Beizzati kabhi nahi bhoolte.", ["Beizzati"]),
    ]),
    dict(n=10, kind="end", trans="punch", cues=[
        ("Yeh thi LAW ONE.", ["LAW", "ONE"]),
        ("Agli law?", ["Agli"]),
        ("Woh aur zyada KHATARNAK hai.", ["KHATARNAK"]),
        ("FOLLOW karo... warna.", ["FOLLOW"]),
    ]),
]


def audio_duration(path):
    err = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    for line in err.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    raise RuntimeError("no duration " + path)


def build():
    t = LEAD
    for b in BEATS:
        ap = os.path.join(AUDIO, f"beat{b['n']:02d}.mp3")
        dur = audio_duration(ap)
        b["dur"], b["start"], b["audio"] = dur, t, ap
        weights = [max(6, len(c.replace(" ", ""))) for c, _ in b["cues"]]
        tot = sum(weights)
        acc, cues = 0.0, []
        for (c, kw), wg in zip(b["cues"], weights):
            cues.append(dict(text=c, kw=kw, t=0.05 + acc / tot * max(0.30, dur - 0.08)))
            acc += wg
        b["cue_times"] = cues
        t += dur + GAP
    return (t - GAP) + TAIL


TOTAL = build()
