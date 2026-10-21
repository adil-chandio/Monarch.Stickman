# 👑 MonarchVoice — The 48 Laws of Power (Easy Urdnglish Deep Storytelling Audiobook)

Complete **Easy Urdnglish (Roman Urdu + English)** Deep Storytelling Audiobook & Production Workflow for **Robert Greene's *The 48 Laws of Power***.

Every single Law (`Law 1` to `Law 48`, plus the Book Preface and Grand Finale) is narrated in engaging conversational Urdnglish with:
- **Real Historical Stories** from the book (*Transgression & Observance of the Law*)
- **Deep Human Psychology**
- **Practical Real-Life & Career Examples**

---

## 🎬 Videos

- [**Ancient Survival — 30-second Easy Urdunglish reel**](video/Ancient_Survival_Easy_Urdunglish_30s_Reel.mp4): new 9:16 illustrated explainer with a walk-cycle character rig (animated cast, not static scenes), Roman Urdu/English captions, narrated audio, and an original score with synchronized sound effects. See [production notes and re-render steps](video/ancient_survival/README.md).
- [**Gol Pahiye Ka Kamaal — 10-second original cartoon**](video/Gol_Pahiye_Ka_Kamaal_10s_Silent.mp4): a new silent 720p prehistoric comedy about a rolling wooden disc, with animated characters, moving props, and English/Roman Urdu on-screen subtitles. The illustrations and animation are newly made for this short; it does not reuse frames from the reference video.
- [**Reference fire scene — 8-second silent edit**](video/Prehistoric_Fire_Reference_8s_720p.mp4): high-resolution edit of the scene in the supplied GIF, **not newly generated animation**. The English/Chinese captions remain. See [source and MIT attribution](video/SOURCE_AND_LICENSE.md).

To reproduce the new cartoon from its illustration assets and Python animation script:

```bash
python3 -m pip install -r video/requirements.txt
python3 video/render_wheel_short.py
```

## 📂 Repository Structure

- **`The_48_Laws_of_Power_Master_Deep_Audiobook.mp3`** — Complete 1-File Master Audiobook (~75 Minutes Non-Stop, Preface + Laws 1–48 + Grand Finale)
- **`Volume_1_Laws_01_to_10_Deep_Storytelling.mp3`** — Volume 1 (Laws 1–10)
- **`Volume_2_Laws_11_to_20_Deep_Storytelling.mp3`** — Volume 2 (Laws 11–20)
- **`Volume_3_Laws_21_to_30_Deep_Storytelling.mp3`** — Volume 3 (Laws 21–30)
- **`Volume_4_Laws_31_to_40_Deep_Storytelling.mp3`** — Volume 4 (Laws 31–40)
- **`Volume_5_Laws_41_to_48_Deep_Storytelling.mp3`** — Volume 5 (Laws 41–48 + Grand Finale)
- **`deep_audio/`** — All 50 individual full-length Deep Storytelling MP3 episodes (`Law_00` through `Law_49`)
- **`audio/`** — Quick Summary Edition (10 Parts covering Laws 1–48)
- **`The_48_Laws_of_Power_Easy_Urdnglish_Guide.md`** — Written Easy Urdnglish Companion Guide for all 48 Laws
- **`compile_audiobook.py`** — Python workflow script that strips ID3/Xing/Info headers from individual MP3 segments and merges them into a seamless CBR MP3 stream

---

## 🛠️ Workflow: How to Re-Compile Audio

```bash
python3 compile_audiobook.py
```
