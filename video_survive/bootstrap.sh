#!/usr/bin/env bash
# Link the shared engine (video_law1) into this film folder, then run.
set -e
cd "$(dirname "$0")"
for f in vlib.py render_v3.py probe.py timeline_v4.py premium_audio.py \
         audio_v3.py audio_v9.py audio_v10.py sfx_v9.py; do
  [ -e "$f" ] || ln -s ../video_law1/$f "$f"
done
[ -e fonts ] || ln -s ../video_law1/fonts fonts
[ -e assets ] || ln -s ../video_law1/assets assets
[ -e audio_v9 ] || ln -s ../video_law1/audio_v9 audio_v9
echo "linked. next:"
echo "  python render_sh.py full   # picture  -> out/survive_silent.mp4"
echo "  python music_sh.py         # score    -> out/music_sh.wav"
echo "  python sfx_sh.py           # effects  -> out/sfx_sh.wav"
echo "  python audio_sh.py         # mix      -> out/mix_sh.wav"
echo "  ffmpeg -i out/survive_silent.mp4 -i out/mix_sh.wav -map 0:v -c:v copy \\"
echo "         -map 1:a -c:a aac -b:a 256k -movflags +faststart -shortest out/Survive_AncientHumans_9x16.mp4"
