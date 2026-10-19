# MonarchVoice — Complete Production Workflow & Chat Log

## 1. Project Overview
- **Source Book:** *The 48 Laws of Power* by Robert Greene (`The+48+Laws+Of+Power.pdf`)
- **Target Language & Style:** Conversational Easy Urdnglish (Roman Urdu + English) with Deep Historical Storytelling, Human Psychology, and Practical Real-Life Examples (~1.5–2 minutes per Law).
- **Voice Model:** Registered via Arena Voice Audition (`voice-00`, `language: "ur"`).

## 2. Production Architecture
1. **Episode Generation (`deep_audio/`):**
   - `Law_00_Book_Preface_Introduction.mp3` — Book Preface & Core Philosophy
   - `Law_01` to `Law_48` — 48 individual full-length Deep Storytelling episodes
   - `Law_49_Book_Grand_Finale_Master_Takeaways.mp3` — Grand Finale & 5 Golden Rules
2. **Volume Compilation (`Volume_1` to `Volume_5`):**
   - Grouped in sets of 10 Laws per Volume (~15 minutes each).
3. **Seamless Master Compilation (`compile_audiobook.py`):**
   - Strips ID3v1/ID3v2 tags and LAME `Info`/`Xing` header frames from each MP3 segment so HTML5 and desktop players read the full ~75-minute duration seamlessly without stopping after the first segment.
   - Outputs `The_48_Laws_of_Power_Master_Deep_Audiobook.mp3` (16.4 MB).
