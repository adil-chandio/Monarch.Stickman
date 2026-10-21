# Ancient Survival — real 3D reel (frame by frame)

Every frame of `video/Ancient_Survival_3D_30s_Reel.mp4` is rasterised from triangles on
the CPU. There are no images, sprites, textures or pre-made models anywhere in the
pipeline: geometry, normals, vertex colours and emission are all generated in Python.

## Files

| file | what it does |
| --- | --- |
| `raster.c` | software rasteriser: z-buffer, toon banding, ink outlines, emission, fog, shadow |
| `rasterlib.py` | ctypes wrapper (`Raster(w, h, fov)`, `.camera()`, `.environment()`, `.render()`) |
| `mesh3d.py` | low-poly primitive builder, 17-joint humanoid rig, pose library, palettes |
| `scenes3d.py` | terrain / trees / rocks / fire / props and the five shots of the reel |
| `render_3d.py` | full-reel driver: 720×1280 render → 1080×1920 upscale, grain, captions, ffmpeg segments |

## Build & render

```bash
gcc -O2 -march=native -shared -fPIC -o libraster.so raster.c -lm      # auto-run by rasterlib
python3 render_3d.py --start 0 --end 720 --segment out.mp4            # whole reel
python3 render_3d.py --start 90 --end 180 --segment seg1.mp4          # a slice, runs in parallel
```

Narration, score and SFX come from the earlier `video/ancient_survival/compose_audio.py`
mix; the picture is muxed over it with ffmpeg (`-c:v copy -c:a aac`).

## Timeline (30 s, 24 fps)

| time | shot | motion |
| --- | --- | --- |
| 0–5 s | moonlit pass | one survivor runs toward camera, camera tracks |
| 5–10 s | campfire | two survivors warm their hands, sparks rise |
| 10–14 s | stone tools | hand-axe raised and shown, spear planted, camera pushes in |
| 14–18 s | travel | trio walks past, camera leads and pans |
| 18–30 s | camp | fire, two figures warming hands, slow pull-back under the closing title |
