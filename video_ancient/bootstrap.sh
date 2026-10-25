#!/usr/bin/env bash
# Link the shared engine (video_law1) + the score/effects from video_survive.
set -e
cd "$(dirname "$0")"
for f in vlib.py render_v3.py probe.py timeline_v4.py premium_audio.py \
         audio_v3.py audio_v9.py audio_v10.py sfx_v9.py; do
  [ -e "$f" ] || ln -s ../video_law1/$f "$f"
done
for d in fonts assets audio_v9; do [ -e "$d" ] || ln -s ../video_law1/$d "$d"; done
echo "linked. next:"
echo "  python render_an.py full     # picture -> out/ancient_silent.mp4"
echo "  ../video_survive -> python music_sh.py / sfx_sh.py   # score + effects"
echo "  python audio_an.py           # mix     -> out/mix_an.wav"
echo "  ffmpeg -i out/ancient_silent.mp4 -i out/mix_an.wav -map 0:v -c:v copy \\"
echo "         -map 1:a -c:a aac -b:a 256k -movflags +faststart -shortest \\"
echo "         out/AncientHumans_LawStyle_9x16.mp4"
