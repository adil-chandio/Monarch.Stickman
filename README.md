**New film:** `video_survive/` — *How Ancient Humans Survived*, 46 s · 9:16 · easy Urdnglish (`video_survive/out/Survive_AncientHumans_9x16.mp4`, see `video_survive/README.md`)

# 👑 MonarchVoice — The 48 Laws of Power (Easy Urdnglish Deep Storytelling Audiobook)

Complete **Easy Urdnglish (Roman Urdu + English)** Deep Storytelling Audiobook & Production Workflow for **Robert Greene's *The 48 Laws of Power***.

Every single Law (`Law 1` to `Law 48`, plus the Book Preface and Grand Finale) is narrated in engaging conversational Urdnglish with:
- **Real Historical Stories** from the book (*Transgression & Observance of the Law*)
- **Deep Human Psychology**
- **Practical Real-Life & Career Examples**

---

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
