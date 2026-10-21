#!/usr/bin/env python3
"""Render the 30-second, vertical Ancient Survival Easy Urdunglish reel.

The edit uses original illustrated scenes, motion graphics, character animation,
beat-synced captions and an original procedural score/SFX mix. No frames from
the reference video are reused. Run from anywhere after installing requirements:

    python3 -m pip install -r video/ancient_survival/requirements.txt
    python3 video/ancient_survival/render_reel.py

For art direction checks:
    python3 video/ancient_survival/render_reel.py --frame-at 16 --frame-output /tmp/fire.png
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageOps

from compose_audio import create_mix

HERE = Path(__file__).resolve().parent
REPO_VIDEO = HERE.parent
ASSETS = HERE / "assets"
FONTS = HERE / "fonts"
BUILD = HERE / "_build"
FINAL = REPO_VIDEO / "Ancient_Survival_Easy_Urdunglish_30s_Reel.mp4"
W, H, FPS, DURATION = 1080, 1920, 24, 30
OVER = (1220, 2166)  # overscan permits smooth handheld/Ken-Burns camera moves
CREAM = (255, 246, 220)
GOLD = (255, 187, 93)
INK = (34, 29, 32)


@dataclass(frozen=True)
class Scene:
    start: float
    end: float
    image: str
    x0: int
    x1: int
    y0: int
    y1: int


SCENES = [
    Scene(0.00, 6.40, "night", 100, 34, 100, 72),
    Scene(6.40, 11.50, "group", 50, 102, 170, 133),
    Scene(11.50, 13.35, "tools", 38, 105, 138, 193),
    Scene(13.35, 14.92, "tracking", 104, 62, 132, 178),
    Scene(14.92, 18.48, "fire", 62, 93, 226, 205),
    Scene(18.48, 22.67, "journey", 42, 106, 169, 144),
    Scene(22.67, 25.50, "group", 100, 56, 134, 175),
    Scene(25.50, 27.65, "journey", 106, 51, 144, 184),
    Scene(27.65, 30.00, "fire", 93, 58, 205, 224),
]
CUTS = [scene.start for scene in SCENES[1:]]

# Captions track the chosen voice's actual phrase pauses (measured from the WAV),
# not a loose estimate from word count. The last 2.3s is a music-only resolution.
CAPTIONS = [
    (0.00, 1.73, "RAAT KA", "JUNGLE..."),
    (1.73, 3.58, "NA PHONE.", "NA SAFE GHAR."),
    (3.58, 6.40, "ANCIENT LOG", "KAISE BACHE?"),
    (6.40, 8.24, "JAWAB?", "TEAMWORK."),
    (8.24, 11.50, "PEHRA + BERRIES", "+ ROOTS"),
    (11.50, 13.35, "SHARP PATHAR", "SE TOOLS"),
    (13.35, 14.92, "MIL KAR", "SHIKAR"),
    (14.92, 18.48, "AAG: ROSHNI,", "GARAMI + KHANA"),
    (18.48, 21.37, "SAB CAVES MEIN", "NAHI REHTE THE!"),
    (21.37, 22.67, "CAMPS BHI", "BADALTE THE"),
    (22.67, 25.50, "ASLI POWER?", "STRENGTH NAHI"),
    (25.50, 27.65, "PLANNING", "+ EK DOOSRE KA SAATH"),
    (27.65, 30.00, "SAATH = SURVIVAL", "MONARCHVOICE"),
]


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def keyed_sprite(path: Path, height: int) -> Image.Image:
    src = Image.open(path).convert("RGB")
    r, g, b = src.split()
    low = ImageChops.darker(r, ImageChops.darker(g, b))
    high = ImageChops.lighter(r, ImageChops.lighter(g, b))
    d = ImageOps.invert(low)
    sat = ImageChops.subtract(high, low)
    alpha = ImageChops.lighter(
        d.point([max(0, min(255, round((v - 11) * 255 / 19))) for v in range(256)]),
        sat.point([max(0, min(255, round((v - 8) * 255 / 15))) for v in range(256)]),
    )
    src.putalpha(alpha)
    src = src.crop(alpha.getbbox())
    return src.resize((round(src.width * height / src.height), height), Image.Resampling.LANCZOS)


def font_for(text: str, wanted: int, max_width: int, black: bool = True) -> ImageFont.FreeTypeFont:
    name = "BarlowCondensed-Black.ttf" if black else "BarlowCondensed-Bold.ttf"
    path = FONTS / name
    size = wanted
    while size > 55:
        f = ImageFont.truetype(str(path), size)
        if f.getlength(text) <= max_width:
            return f
        size -= 3
    return ImageFont.truetype(str(path), size)


def text_center(d: ImageDraw.ImageDraw, text: str, y: int,
                font: ImageFont.FreeTypeFont, fill: tuple[int, ...],
                stroke: int = 0) -> None:
    x = W // 2
    d.text((x + 6, y + 8), text, font=font, anchor="mt",
           fill=(20, 14, 16, 205), stroke_width=stroke + 5,
           stroke_fill=(20, 14, 16, 125))
    d.text((x, y), text, font=font, anchor="mt", fill=fill,
           stroke_width=stroke, stroke_fill=INK + (255,))


def caption_patch(first: str, second: str, final: bool = False) -> Image.Image:
    layer = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f1 = font_for(first, 122 if not final else 128, 972)
    f2 = font_for(second, 118 if not final else 74, 964)
    text_center(d, first, 18, f1, CREAM + (255,), 6)
    text_center(d, second, 133 if not final else 157, f2,
                GOLD + (255,), 6 if not final else 4)
    return layer


def vignette() -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(H):
        bottom = ease((y - 1190) / 570) * 173
        top = (1 - ease(y / 390)) * 98
        a = round(max(top, bottom))
        if a:
            d.line((0, y, W, y), fill=(18, 15, 21, a), width=1)
    return overlay


def glow() -> Image.Image:
    size = 760
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for r in range(370, 18, -4):
        a = round((1 - r / 385) ** 1.45 * 55)
        if a:
            d.ellipse((size // 2 - r, size // 2 - r,
                       size // 2 + r, size // 2 + r),
                      fill=(255, 140, 49, a))
    return layer


class Reel:
    def __init__(self) -> None:
        self.plates = {
            key: ImageOps.fit(Image.open(ASSETS / f"scene_{key}.png").convert("RGB"),
                              OVER, method=Image.Resampling.LANCZOS)
            for key in ("night", "group", "tools", "tracking", "fire", "journey")
        }
        self.runner = keyed_sprite(REPO_VIDEO / "assets" / "caveperson_run.png", 445)
        # Purple-slate lighting integrates the original sprite into this night plate.
        alpha = self.runner.getchannel("A")
        tinted = Image.blend(self.runner.convert("RGB"),
                             Image.new("RGB", self.runner.size, (45, 44, 58)), 0.28)
        tinted.putalpha(alpha)
        self.runner = tinted
        self.captions = [caption_patch(a, b, i == len(CAPTIONS) - 1)
                         for i, (_, _, a, b) in enumerate(CAPTIONS)]
        self.vignette = vignette()
        self.fire_glow = glow()
        self.tag_font = ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), 36)
        self.hook_font1 = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), 157)
        self.hook_font2 = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), 153)

    def scene(self, t: float) -> tuple[Image.Image, Scene]:
        info = next((s for s in SCENES if s.start <= t < s.end), SCENES[-1])
        p = ease((t - info.start) / (info.end - info.start))
        x = round(info.x0 + (info.x1 - info.x0) * p)
        y = round(info.y0 + (info.y1 - info.y0) * p)
        # Momentary impact shudder during hand-knapped flint closeups.
        if info.image == "tools":
            for beat in (11.63, 12.02, 12.55, 12.96):
                if 0 <= t - beat < 0.08:
                    x += round(4 * math.sin(117 * t))
                    y += round(3 * math.cos(129 * t))
        x = max(0, min(OVER[0] - W, x))
        y = max(0, min(OVER[1] - H, y))
        return self.plates[info.image].crop((x, y, x + W, y + H)), info

    def night_motion(self, im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        # Moonlit wind and a running caveperson give real motion to the hook shot.
        for i in range(9):
            x = ((i * 174 + t * (34 + i % 3 * 13)) % 1320) - 100
            y = 750 + (i * 171) % 650
            d.arc((x - 100, y - 10, x + 80, y + 20), 170, 345,
                  fill=(224, 219, 207, 36), width=2)
        x = -565 + 241 * t
        if -self.runner.width < x < W:
            y = round(1488 + 7 * math.sin(14 * t))
            d.ellipse((x + 80, 1467, x + self.runner.width - 64, 1507),
                      fill=(12, 10, 18, 51))
            im.paste(self.runner, (round(x), y - self.runner.height),
                     self.runner.getchannel("A"))
        # Subtle flash early on punctuates the opening impact, without inventing a fire.
        flash = max(0.0, 1 - abs(t - 0.28) / 0.12)
        if flash:
            d.rectangle((0, 0, W, H), fill=(202, 198, 206, round(58 * flash)))

    @staticmethod
    def group_motion(im: Image.Image, t: float, callback: bool = False) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        p = ease((t - (22.67 if callback else 8.18)) / 0.5)
        if p <= 0:
            return
        # Two ink-sketch cues guide the eye: lookout, then shared food gathering.
        for x, y, r in ((555, 570, 85), (765, 1050, 73), (305, 1360, 76)):
            a = round(p * (82 + 20 * math.sin(t * 4 + x)))
            d.arc((x - r, y - r, x + r, y + r), 205, 490,
                  fill=(255, 193, 95, a), width=4)
        if not callback:
            for i in range(5):
                xx = 733 + i * 24 + 7 * math.sin(t * 4 + i)
                yy = 1080 + i * 17 + 10 * math.cos(t * 3.2 + i)
                d.ellipse((xx, yy, xx + 5, yy + 5), fill=(255, 210, 125, 134))

    @staticmethod
    def tools_motion(im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        for j, beat in enumerate((11.63, 12.02, 12.55, 12.96, 13.15)):
            age = t - beat
            if 0 < age < 0.38:
                for k in range(5):
                    angle = (j * 0.8 + k * 1.6)
                    dist = 18 + 165 * age * (0.5 + k / 7)
                    x = 561 + dist * math.cos(angle)
                    y = 837 + dist * math.sin(angle) + 240 * age * age
                    radius = max(1, round(6 - age * 10))
                    d.polygon([(x, y - radius), (x + radius, y + radius),
                               (x - radius, y + radius)],
                              fill=(255, 209, 126, round(175 * (1 - age / 0.38))))
        # Tiny parallax glint follows the worked blade edge.
        glint = 0.55 + 0.45 * math.sin(18 * t)
        d.line((542, 779, 587, 746), fill=(255, 234, 184, round(100 * glint)), width=3)

    @staticmethod
    def tracking_motion(im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        p = ease((t - 13.52) / 0.52)
        if p:
            # A transient trail connects the hoofprints to the distant deer.
            for i in range(7):
                a = p * (i / 7)
                x = 465 - 130 * a
                y = 1460 - 675 * a
                d.ellipse((x - 4, y - 4, x + 4, y + 4),
                          fill=(255, 196, 104, round(176 * p)))

    def fire_motion(self, im: Image.Image, t: float, ending: bool = False) -> None:
        intensity = 0.76 + 0.24 * math.sin(21 * t)
        warm = self.fire_glow.copy()
        warm.putalpha(warm.getchannel("A").point(lambda a: round(a * intensity)))
        im.paste(warm, (W // 2 - 380, 1075), warm.getchannel("A"))
        d = ImageDraw.Draw(im, "RGBA")
        for j in range(18):
            drift = (t * (63 + j % 5 * 10) + j * 79) % 385
            x = 532 + 115 * math.sin(t * 0.8 + j * 3.57) * (drift / 385)
            y = 1449 - drift
            r = 2 + j % 3
            alpha = round(196 * (1 - drift / 385) ** 1.4)
            d.ellipse((x - r, y - r, x + r, y + r),
                      fill=(255, 184 + j % 3 * 14, 72, alpha))
        if ending:
            for j in range(8):
                x = (90 + 121 * j + 15 * math.sin(t * 1.5 + j))
                y = 620 + (j * 131) % 520
                d.ellipse((x - 2, y - 2, x + 2, y + 2),
                          fill=(255, 215, 137, 116))

    @staticmethod
    def journey_motion(im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        for j in range(11):
            x = (j * 174 + t * 36) % 1260 - 90
            y = 1080 + (j * 105) % 520
            d.arc((x - 18, y - 6, x + 34, y + 8), 180, 355,
                  fill=(85, 75, 62, 57), width=2)
        for j in range(4):
            phase = (t * 2.1 + j * 0.46) % 1
            x = 474 + j * 88 - phase * 58
            y = 1495 - phase * 33
            r = 5 + 12 * phase
            d.ellipse((x - r, y - r / 2, x + r, y + r / 2),
                      fill=(181, 154, 113, round(76 * (1 - phase))))

    def title(self, im: Image.Image, t: float, scene: Scene) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        # Small editorial header; never placed in the top app-control row.
        d.text((60, 111), "MONARCHVOICE  /  SURVIVAL FILE 01",
               font=self.tag_font, fill=(255, 226, 171, 234),
               stroke_width=2, stroke_fill=(21, 20, 23, 190))
        # Story progress indicator also creates a visual forward pull.
        d.rounded_rectangle((60, 178, 1018, 185), radius=3, fill=(255, 246, 220, 80))
        d.rounded_rectangle((60, 178, 60 + max(7, round(958 * t / DURATION)), 185),
                            radius=3, fill=GOLD + (235,))
        if t < 3.52:
            fade = min(1.0, t / 0.18, (3.52 - t) / 0.24)
            if fade > 0:
                layer = Image.new("RGBA", (W, 560), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                text_center(ld, "KYA TUM", 12, self.hook_font1, CREAM + (255,), 6)
                text_center(ld, "BACH PATE?", 163, self.hook_font2, GOLD + (255,), 6)
                layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(layer, (0, 318 + round(24 * (1 - fade))), layer.getchannel("A"))
        elif 6.40 <= t < 8.35:
            fade = min(1.0, (t - 6.40) / 0.22, (8.35 - t) / 0.20)
            if fade > 0:
                layer = Image.new("RGBA", (W, 210), (0, 0, 0, 0))
                text_center(ImageDraw.Draw(layer), "TEAMWORK", 0,
                            font_for("TEAMWORK", 185, 974), GOLD + (255,), 6)
                layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(layer, (0, 294), layer.getchannel("A"))
        elif t >= 27.65:
            fade = ease((t - 27.65) / 0.36)
            layer = Image.new("RGBA", (W, 380), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            text_center(ld, "SAATH HI", 5, font_for("SAATH HI", 157, 970),
                        CREAM + (255,), 6)
            text_center(ld, "SUPERPOWER HAI.", 150,
                        font_for("SUPERPOWER HAI.", 143, 970), GOLD + (255,), 6)
            layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
            im.paste(layer, (0, 312), layer.getchannel("A"))

    def caption(self, im: Image.Image, t: float) -> None:
        for i, (start, end, _, _) in enumerate(CAPTIONS):
            if start <= t < end:
                # The caption is a rhythmic punch-in, then breathes before the cut.
                fade = min(1.0, (t - start) / 0.16, (end - t) / 0.14)
                fade = max(0.0, ease(fade))
                patch = self.captions[i]
                if fade < 0.999:
                    patch = patch.copy()
                    patch.putalpha(patch.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(patch, (0, 1437 + round(26 * (1 - fade))),
                         patch.getchannel("A"))
                break

    @staticmethod
    def transition(im: Image.Image, t: float) -> None:
        for cut in CUTS:
            distance = abs(t - cut)
            if distance < 0.115:
                power = (1 - distance / 0.115) ** 1.5
                d = ImageDraw.Draw(im, "RGBA")
                d.rectangle((0, 0, W, H), fill=(250, 222, 172, round(165 * power)))
                # One rough diagonal ink sweep mimics turning a storybook page.
                x = ((t - cut + 0.115) / 0.23) * (W + 400) - 220
                d.polygon([(x - 145, 0), (x - 102, 0), (x + 150, H),
                           (x + 106, H)], fill=(85, 62, 48, round(72 * power)))
                break

    def frame(self, t: float) -> Image.Image:
        im, scene = self.scene(t)
        if scene.image == "night":
            self.night_motion(im, t)
        elif scene.image == "group":
            self.group_motion(im, t, callback=t >= 22.67)
        elif scene.image == "tools":
            self.tools_motion(im, t)
        elif scene.image == "tracking":
            self.tracking_motion(im, t)
        elif scene.image == "fire":
            self.fire_motion(im, t, ending=t >= 27.65)
        elif scene.image == "journey":
            self.journey_motion(im, t)
        im.paste(self.vignette, (0, 0), self.vignette.getchannel("A"))
        self.transition(im, t)
        self.title(im, t, scene)
        self.caption(im, t)
        return im


def ffmpeg() -> str:
    result = shutil.which("ffmpeg")
    if result:
        return result
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Install video/ancient_survival/requirements.txt") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_video(reel: Reel, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert proc.stdin is not None
        for n in range(FPS * DURATION):
            proc.stdin.write(reel.frame(n / FPS).tobytes())
            if n % (FPS * 5) == 0:
                print(f"Visuals: {n // FPS:02d} / {DURATION}s", flush=True)
        proc.stdin.close()
        assert proc.stderr is not None
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg video encode failed: {err}")
    except BaseException:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        proc.wait()
        raise


def mux(video: Path, audio: Path, output: Path) -> None:
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", "30", "-movflags", "+faststart", str(output)]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-at", type=float, help="Render one frame as a preview PNG")
    parser.add_argument("--frame-output", type=Path)
    parser.add_argument("--output", type=Path, default=FINAL)
    parser.add_argument("--skip-visuals", action="store_true",
                        help="Reuse _build/visual.mp4 when only remixing audio")
    args = parser.parse_args()
    reel = Reel()
    if args.frame_at is not None:
        if not 0 <= args.frame_at < DURATION:
            parser.error("--frame-at must be within [0, 30)")
        out = args.frame_output or Path("/tmp/survival-preview.png")
        reel.frame(args.frame_at).save(out)
        print(f"Preview: {out}")
        return
    visual = BUILD / "visual.mp4"
    if not args.skip_visuals or not visual.exists():
        render_video(reel, visual)
    soundtrack = create_mix(BUILD / "final_mix.wav")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mux(visual, soundtrack, args.output)
    print(f"Rendered {args.output}: 30s, 1080x1920, 24fps, narrated stereo audio")


if __name__ == "__main__":
    main()
