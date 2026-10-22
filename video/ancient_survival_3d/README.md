# Ancient Survival — real 3D reel (frame by frame)

Every frame of `video/Ancient_Survival_3D_30s_Reel.mp4` is rasterised from triangles on
the CPU. There are no images, sprites, photographs or painted plates anywhere in the
pipeline: geometry, normals, UVs, materials and emission are generated at build/render
time, and the renderer shades every pixel procedurally.

The heads are real human anatomy: they come from **Google's GNM Head** parametric scan
model (Apache-2.0, © 2026 Google LLC), baked offline into `heads.npz` by
`tools/bake_gnm_heads.py` (four distinct identities, eyelids parted and eyeballs
positioned at bake time). Bodies, clothing, terrain, trees, rocks and fire remain
procedural geometry.

## Files

| file | what it does |
| --- | --- |
| `raster.c` | software rasteriser v3: near-plane clipping, z-buffer, 1024² shadow map (3×3 PCF, grazing-angle bias), two point lights, screen-space AO, depth of field, bloom, ACES + filmic S-curve grade, procedural sky (gradient / moon disc / stars / milky way / clouds), vignette + grain |
| material shader | per-pixel procedural surfaces: skin (pores, pore dots, mottling, capillaries, subsurface wrap, sheen), woven hide, hair strands, stone grain + lichen, leaf translucency, corneas, bark, soil |
| `rasterlib.py` | ctypes wrapper (`Raster(w, h, fov)`, `.camera()`, `.environment()`, `.render()`) |
| `mesh3d.py` | uv/material-aware primitive builder, welded smooth normals, 17-joint rig and pose library, **GNM scanned heads** (+ skull-grown hair shell, brow/lip/beard shading), hands with fingers, palettes |
| `heads.npz` | four baked GNM identities: 17,821 verts / 35,324 tris each, with eye/lip/teeth masks, facial group masks |
| `tools/bake_gnm_heads.py` | one-off bake: identity coefficients → vertices, eyelid aperture, group masks (needs Google's `gnm_head.npz`) |
| `scenes3d.py` | terrain, layered mountain ranges, pine/oak trees, multi-lobe boulders, ferns, grass, fire + point light, props and the five shots |
| `render_3d.py` | full-reel driver: 960×1707 render → 1080×1920, grain, captions, ffmpeg segments |

## Build & render

```bash
gcc -O2 -march=native -shared -fPIC -o libraster.so raster.c -lm      # auto-run by rasterlib
python3 render_3d.py --start 0 --end 720 --segment out.mp4            # whole reel
python3 render_3d.py --start 90 --end 180 --segment seg1.mp4          # a slice, runs in parallel
```

Narration, score and SFX come from `video/ancient_survival/compose_audio.py`; the picture
is muxed over it with ffmpeg (`-c:v copy -c:a aac`).

## Timeline (30 s, 24 fps)

| time | shot | motion |
| --- | --- | --- |
| 0–5 s | moonlit pass | one survivor runs toward camera, camera tracks, layered ridges behind |
| 5–10 s | campfire | two survivors warm their hands, fire casts real point light, sparks rise |
| 10–14 s | stone tools | knapped blade held up and shown, spear planted, camera pushes in |
| 14–18 s | travel | trio walks past, camera leads and pans |
| 18–30 s | camp | fire, two figures warming hands, slow pull-back under the closing title |

## Realism pass (this revision)

* **Heads**: GNM Head scan geometry, four identities (man, woman, elder, second woman);
  eyelids opened at bake time, irises/pupils from GNM's own eye components, procedural
  hair grown off the skull normals (hairline follows the brow and nape), brow / lip /
  beard shading from mesh groups.
* **Skin**: continuous per-pixel pore field (two octaves + thresholded pore dots),
  melanin mottling, capillary reddening, wrap diffuse, Fresnel sheen, distance LOD so
  the detail never aliases into gravel.
* **Light**: no more toon banding — continuous wrapped diffuse plus a filmic S-curve
  grade, cool shadows / warm highlights, grain, vignette, depth of field on every shot.
* **Cast**: hands with fingers and thumbs, joint blending spheres, hide tunics with a
  flared hem, blinking eye state plumbed through every shot.
* **Environment**: noise-displaced mountain ridges with snow lines and aerial haze,
  five-tier pines with ragged silhouettes, denser grass and stone scatter.

## Licences

* GNM Head (geometry in `heads.npz`): Apache License 2.0, © 2026 Google LLC —
  <https://github.com/google/GNM>. `heads.npz` is a baked derivative (four sampled
  identities) of `gnm_head.npz` from that project.
* Everything else in this folder: original work for MonarchVoice.
