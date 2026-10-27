"""Step 3: cut, grade, title, subtitle and mix the ad -> final/rolex_spec_ad.mp4.

Usage:  python render.py            # full quality
        python render.py --draft    # faster encode, same timing
"""

import argparse
import json
import subprocess
import urllib.request

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
    start = entry.get("start", 1.0 if entry["duration"] >= seconds + 2 else 0.0)
    # Optional reframing: "zoom" punches in, "anchor_x" slides the crop (0 = left, 0.5 = centre, 1 = right).
    zoom, ax = entry.get("zoom", 1.0), entry.get("anchor_x", 0.5)
    frame = (f"scale={round(W * zoom)}:{round(H * zoom)}:force_original_aspect_ratio=increase,"
             f"crop={W}:{H}:(iw-{W})*{ax}:(ih-{H})/2")
    run(["ffmpeg", "-y", "-ss", str(start), "-i", str(src), "-t", f"{seconds:.3f}", "-an",
         "-vf", f"{frame},fps={config.FPS},setsar=1,{GRADE}",
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


def title(text, font, size, tracking, center_y, start, end, center_x=W / 2):
    rgba = text_image(text, font, size, tracking)
    clip = ImageClip(rgba[..., :3]).with_mask(ImageClip(rgba[..., 3] / 255.0, is_mask=True))
    pos = (int(center_x - rgba.shape[1] / 2), int(center_y - rgba.shape[0] / 2))
    return (clip.with_start(start).with_duration(end - start).with_position(pos)
            .with_effects([vfx.CrossFadeIn(config.TEXT_FADE), vfx.CrossFadeOut(config.TEXT_FADE)]))


def subtitle(cue):
    """Subtitle in the lower letterbox bar, so it never sits on the picture."""
    rgba = text_image(cue["text"], config.FONT_REGULAR, config.SUBTITLE_SIZE, 0.06)
    clip = ImageClip(rgba[..., :3]).with_mask(ImageClip(rgba[..., 3] / 255.0, is_mask=True))
    pos = ((W - rgba.shape[1]) // 2, int(H - BAR / 2 - rgba.shape[0] / 2))
    return (clip.with_start(cue["start"]).with_duration(cue["end"] - cue["start"]).with_position(pos)
            .with_effects([vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.15)]))


# ---------------------------------------------------------------- audio

def sfx_file(mixkit_id):
    """Mixkit sound effects are free to use (Mixkit licence) but not ours to redistribute,
    so they're fetched on first render instead of committed."""
    path = config.SFX_DIR / f"mixkit-{mixkit_id}.mp3"
    if not path.exists():
        config.SFX_DIR.mkdir(exist_ok=True)
        url = f"https://assets.mixkit.co/active_storage/sfx/{mixkit_id}/{mixkit_id}-preview.mp3"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
    return path


def sfx_events(starts, total):
    """(mixkit id, start, length, gain dB, filter) for every ambience in the cut."""
    events = []
    for shot in config.SHOTS:
        t0 = starts[shot["id"]]
        length = shot["duration"] + config.CROSSFADE + config.SFX_FADE
        events += [(i, max(t0 - config.SFX_FADE / 2, 0), length, g, f) for i, g, f in shot["sfx"]]
    end = starts["end"]
    events += [(i, end, total - end, g, f) for i, g, f in config.END_CARD_SFX]
    wid, wgain = config.HERO_WHOOSH
    events.append((wid, max(starts[config.SHOTS[-1]["id"]] - 0.6, 0), 1.6, wgain, ""))
    return events


def mix_audio(vo_lines, total, out):
    inputs, filters, labels = [], [], []
    for i, line in enumerate(vo_lines):
        inputs += ["-i", line["file"]]
        ms = int(line["start"] * 1000)
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,volume=4dB,adelay={ms}|{ms}[v{i}]")
        labels.append(f"[v{i}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad,atrim=0:{total}[vo]")

    # Ambience bed: each shot's sounds, trimmed to the shot and crossfaded at the cuts.
    fx = []
    for mixkit_id, start, length, gain, extra in sfx_events(config.shot_starts(), total):
        n = len(inputs) // 2
        inputs += ["-i", str(sfx_file(mixkit_id))]
        ms = int(start * 1000)
        chain = [f"aresample=48000,aformat=channel_layouts=stereo,atrim=0:{length:.3f}", extra,
                 f"volume={gain}dB,afade=t=in:d={config.SFX_FADE},"
                 f"afade=t=out:st={max(length - config.SFX_FADE, 0):.3f}:d={config.SFX_FADE},adelay={ms}|{ms}"]
        filters.append(f"[{n}:a]" + ",".join(c for c in chain if c) + f"[f{n}]")
        fx.append(f"[f{n}]")
    filters += [
        f"{''.join(fx)}amix=inputs={len(fx)}:normalize=0,apad,atrim=0:{total},"
        f"afade=t=out:st={total - 1.2}:d=1.2[bed]",
        "[vo]asplit=2[vo_out][vo_key]",
        # Duck the ambience a few dB while the narrator speaks.
        "[bed][vo_key]sidechaincompress=threshold=0.02:ratio=4:attack=60:release=500[ducked]",
        # Loudness-normalise to -16 LUFS, the usual target for online video.
        "[ducked][vo_out]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]",
    ]
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
         "-t", str(total), "-c:a", "pcm_s16le", str(out)])


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

    hero, end = starts[config.SHOTS[-1]["id"]], starts["end"]
    titles = [
        # The hero watch fills the frame top to bottom, so the name sits in the dark space beside it.
        title(config.HERO_TITLE, config.FONT_REGULAR, 92, 0.42, H / 2, hero + 0.5, end + 0.2, center_x=W * 0.18),
        title(config.END_TITLE, config.FONT_LIGHT, 68, 0.12, H / 2 - 18, end + 0.3, total),
        title(config.END_DISCLAIMER, config.FONT_REGULAR, 24, 0.16, H / 2 + 62, end + 0.7, total),
    ]
    subs = [subtitle(c) for line in vo_lines for c in line["cues"]]
    bars = [ColorClip((W, BAR), color=(0, 0, 0)).with_duration(total).with_position((0, y))
            for y in (0, H - BAR)]
    video = CompositeVideoClip([*layers, *titles, *bars, *subs], size=(W, H)).with_duration(total)

    silent = config.WORK_DIR / "picture.mp4"
    video.write_videofile(str(silent), fps=config.FPS, codec="libx264", audio=False,
                          preset="veryfast" if args.draft else "slow",
                          ffmpeg_params=["-crf", "22" if args.draft else "16", "-pix_fmt", "yuv420p"],
                          logger="bar")

    audio = config.WORK_DIR / "mix.wav"
    mix_audio(vo_lines, total, audio)
    config.FINAL_DIR.mkdir(exist_ok=True)
    run(["ffmpeg", "-y", "-i", str(silent), "-i", str(audio), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
         "-shortest", str(config.OUTPUT)])
    print(f"\nWrote {config.OUTPUT}")


if __name__ == "__main__":
    main()
