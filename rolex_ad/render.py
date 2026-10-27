"""Step 3: cut, grade, title and mix the ad -> final/rolex_spec_ad.mp4.

Usage:  python render.py            # full quality
        python render.py --draft    # faster encode, same timing
"""

import argparse
import json
import subprocess

import numpy as np
from moviepy import ColorClip, CompositeVideoClip, ImageClip, VideoFileClip, vfx
from PIL import Image, ImageDraw, ImageFont

import config

W, H = config.WIDTH, config.HEIGHT
BAR = round((H - W / config.LETTERBOX_RATIO) / 2)   # 138px top and bottom


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


# ---------------------------------------------------------------- clips

def normalise(entry, seconds):
    """Trim, scale-to-cover, crop to 1920x1080 and conform to 24fps, no audio."""
    src = config.CLIPS_DIR / entry["file"]
    dst = config.WORK_DIR / "norm" / f"shot{entry['shot']}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Skip the first second of stock clips (often a camera settle or fade) when there's room.
    start = 1.0 if entry["duration"] >= seconds + 2 else 0.0
    run(["ffmpeg", "-y", "-ss", str(start), "-i", str(src), "-t", f"{seconds:.3f}", "-an",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={config.FPS},setsar=1,{GRADE}",
         "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", str(dst)])
    return dst


def motion_score(clip):
    """Mean absolute luma change between frames 0.5s apart, on a 160x90 thumbnail (0-255)."""
    times = np.linspace(0, max(clip.duration - 0.6, 0.1), 6)
    diffs = []
    for t in times:
        a, b = (np.asarray(Image.fromarray(clip.get_frame(x)).convert("L").resize((160, 90)), float)
                for x in (t, min(t + 0.5, clip.duration - 0.05)))
        diffs.append(np.abs(a - b).mean())
    return float(np.median(diffs))


def ken_burns(path, seconds):
    """Slow centred push-in, 100% -> 108%. Upscaling first keeps zoompan's steps sub-pixel smooth."""
    dst = path.with_name(path.stem + "_kb.mp4")
    frames = max(round(seconds * config.FPS) - 1, 1)
    z = f"1+{config.KEN_BURNS_END_SCALE - 1}*on/{frames}"
    run(["ffmpeg", "-y", "-i", str(path), "-vf",
         f"scale={W * 2}:{H * 2}:flags=lanczos,zoompan=z='{z}':d=1:s={W}x{H}:fps={config.FPS}"
         ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
         "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", str(dst)])
    return dst


# ---------------------------------------------------------------- grade

# Applied by ffmpeg to every clip as it is normalised, so footage from different
# shooters lands in one look; titles and bars are composited later, ungraded.
GRADE = ",".join([
    "eq=saturation=0.72:contrast=1.05",                        # ~28% desaturated
    "curves=all='0/0 0.07/0 0.3/0.25 0.7/0.72 1/0.98'",        # crushed blacks, soft S
    "colorbalance=rh=0.07:gh=0.025:bh=-0.06:rm=0.02:bm=-0.02",  # warm highlights
    "vignette=angle=PI/4.5",                                   # subtle edge falloff
])


# ---------------------------------------------------------------- titles

def text_image(text, font_path, size, tracking):
    """White text with wide letter-spacing (tracking is a fraction of the font size)."""
    font = ImageFont.truetype(str(font_path), size)
    gap = size * tracking
    advances = [font.getlength(ch) for ch in text]
    width = int(sum(advances) + gap * (len(text) - 1)) + 8
    asc, desc = font.getmetrics()
    img = Image.new("RGBA", (width, asc + desc + 8), (255, 255, 255, 0))
    draw, x = ImageDraw.Draw(img), 4
    for ch, adv in zip(text, advances):
        draw.text((x, 4), ch, font=font, fill=(255, 255, 255, 255))
        x += adv + gap
    return np.asarray(img)


def title(text, font, size, tracking, center_y, start, end):
    rgba = text_image(text, font, size, tracking)
    clip = ImageClip(rgba[..., :3]).with_mask(ImageClip(rgba[..., 3] / 255.0, is_mask=True))
    pos = ((W - rgba.shape[1]) // 2, int(center_y - rgba.shape[0] / 2))
    return (clip.with_start(start).with_duration(end - start).with_position(pos)
            .with_effects([vfx.CrossFadeIn(config.TEXT_FADE), vfx.CrossFadeOut(config.TEXT_FADE)]))


# ---------------------------------------------------------------- audio

def mix_audio(vo_lines, total, out):
    inputs, filters, labels = [], [], []
    for i, line in enumerate(vo_lines):
        inputs += ["-i", line["file"]]
        ms = int(line["start"] * 1000)
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
        labels.append(f"[v{i}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad,atrim=0:{total}[vo]")

    music = config.MUSIC.exists()
    if music:
        m = len(vo_lines)
        inputs += ["-i", str(config.MUSIC)]
        mstart = config.shot_starts()[config.MUSIC_START_SHOT]
        ms = int(mstart * 1000)
        filters += [
            "[vo]asplit=2[vo_out][vo_key]",
            f"[{m}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total - mstart},"
            f"volume={config.MUSIC_GAIN_DB}dB,afade=t=in:d={config.MUSIC_FADE_IN},"
            f"afade=t=out:st={total - mstart - config.MUSIC_FADE_OUT}:d={config.MUSIC_FADE_OUT},"
            f"adelay={ms}|{ms},apad,atrim=0:{total}[bed]",
            # Duck the bed roughly 6-8dB while the narrator speaks.
            "[bed][vo_key]sidechaincompress=threshold=0.015:ratio=6:attack=80:release=700:makeup=1[ducked]",
            "[ducked][vo_out]amix=inputs=2:normalize=0[mix]",
        ]
        final = "[mix]"
    else:
        final = "[vo]"
    filters.append(f"{final}alimiter=limit=0.95[out]")
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
         "-t", str(total), "-c:a", "pcm_s16le", str(out)])
    return music


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true", help="faster, lower-quality encode")
    args = ap.parse_args()

    manifest = json.loads(config.MANIFEST.read_text())
    vo_lines = json.loads((config.WORK_DIR / "vo" / "voiceover.json").read_text())
    starts, total = config.shot_starts(), config.total_duration()

    layers = [ColorClip((W, H), color=(0, 0, 0)).with_duration(total)]
    for shot in config.SHOTS:
        entry = manifest[str(shot["id"])]
        seconds = shot["duration"] + config.CROSSFADE      # tail overlaps the next shot
        path = normalise(entry, seconds)
        clip = VideoFileClip(str(path))
        seconds = min(seconds, clip.duration)
        kb = shot["ken_burns"]
        if kb == "auto":
            score = motion_score(clip)
            kb = score < 3.0
            print(f"shot {shot['id']}: motion {score:.2f} -> {'Ken Burns' if kb else 'as shot'}")
        if kb:
            clip.close()
            clip = VideoFileClip(str(ken_burns(path, seconds)))
            seconds = min(seconds, clip.duration)
        clip = clip.subclipped(0, seconds)
        effects = [] if shot["id"] == 1 else [vfx.CrossFadeIn(config.CROSSFADE)]
        if shot["id"] == config.SHOTS[-1]["id"]:
            effects.append(vfx.CrossFadeOut(config.CROSSFADE))  # dissolve to the black end card
        layers.append(clip.with_start(starts[shot["id"]]).with_effects(effects))

    hero, end = starts[8], starts["end"]
    titles = [
        title(config.HERO_TITLE, config.FONT_REGULAR, 104, 0.42, H - BAR - 120, hero + 1.0, end + 0.3),
        title(config.END_TITLE, config.FONT_LIGHT, 68, 0.12, H / 2 - 18, end + 0.6, total),
        title(config.END_DISCLAIMER, config.FONT_REGULAR, 24, 0.16, H / 2 + 62, end + 1.2, total),
    ]
    bars = [ColorClip((W, BAR), color=(0, 0, 0)).with_duration(total).with_position((0, y))
            for y in (0, H - BAR)]
    video = CompositeVideoClip([*layers, *titles, *bars], size=(W, H)).with_duration(total)

    silent = config.WORK_DIR / "picture.mp4"
    video.write_videofile(str(silent), fps=config.FPS, codec="libx264", audio=False,
                          preset="veryfast" if args.draft else "slow",
                          ffmpeg_params=["-crf", "22" if args.draft else "16", "-pix_fmt", "yuv420p"],
                          logger="bar")

    audio = config.WORK_DIR / "mix.wav"
    used_music = mix_audio(vo_lines, total, audio)
    config.FINAL_DIR.mkdir(exist_ok=True)
    run(["ffmpeg", "-y", "-i", str(silent), "-i", str(audio), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
         "-shortest", str(config.OUTPUT)])
    print(f"\nWrote {config.OUTPUT}")
    if not used_music:
        print("No music.mp3 found — rendered with voiceover only.")


if __name__ == "__main__":
    main()
