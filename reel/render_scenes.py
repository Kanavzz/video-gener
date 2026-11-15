"""Turn each scene's AI image + AI voice lines into an animated clip.

Smooth camera moves (pan / push-in / comedic punch-ins) are drawn with
sub-pixel affine transforms in Pillow, so there's none of zoompan's jitter.
Voices are laid out back to back; the exact line timings become the subtitle
cues, and each scene's length follows its dialogue (min 8 s).

Inputs:  build/images/<id>.png, build/voice/<id>_<n>.wav (make_voices.py)
Outputs: build/clips/<id>.mp4, build/cues/<id>.json, build/durations.json
"""
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from scenes import SCENES

HERE = Path(__file__).parent
B = HERE / "build"
W, H, FPS, RATE = 1080, 1920, 30, 24000
LEAD, GAP, TAIL, MIN_DUR = 0.45, 0.35, 0.7, 8.0
LEADS = {"scene5": 1.7}      # time to read the notice before anyone speaks
MIN_DURS = {"scene5": 9.3}   # leave the context box on screen long enough to read

# Camera keyframes per scene: (time or "lineN" / "lineN_end", cx, cy, zoom).
# cx, cy are the frame centre as fractions of the image; zoom 1 = full width.
CAMERA = json.loads((HERE / "camera.json").read_text())


def news_sting():
    """A short synthesized TV-news sting (no samples, so no licensing issue)."""
    t = np.arange(int(1.6 * RATE)) / RATE
    out = np.zeros_like(t)
    for start, freqs in [(0.0, [392, 494, 587]), (0.16, [440, 554, 659]), (0.32, [523, 659, 784, 1046])]:
        seg = t >= start; tt = t[seg] - start
        env = np.minimum(tt / 0.01, 1) * np.exp(-tt * (2.2 if start == 0.32 else 9))
        tone = sum(np.sign(np.sin(2 * np.pi * f * tt)) * 0.35 + np.sin(2 * np.pi * f * tt) for f in freqs)
        out[seg] += tone * env
    out = np.convolve(out, np.ones(6) / 6, mode="same")  # soften the square-wave edge
    return (out / np.abs(out).max() * 0.18).astype(np.float32)


STING = news_sting()


def wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768, w.getframerate()


def read_float(path):
    import soundfile
    data, rate = soundfile.read(str(path), dtype="float32")
    return data, rate


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def camera_at(keys, t):
    if t <= keys[0][0]:
        return keys[0][1:]
    for (t0, *a), (t1, *b) in zip(keys, keys[1:]):
        if t <= t1:
            k = ease((t - t0) / max(1e-6, t1 - t0))
            return [u + (v - u) * k for u, v in zip(a, b)]
    return keys[-1][1:]


def resolve(keys, starts, ends, dur):
    out = []
    for t, *rest in keys:
        if isinstance(t, str):
            m = re.fullmatch(r"(?:line(\d+)(_end)?|end)([+-][\d.]+)?", t)
            base = dur if t.startswith("end") else (ends if m.group(2) else starts)[int(m.group(1))]
            t = base + float(m.group(3) or 0)
        out.append([float(t), *rest])
    return sorted(out, key=lambda k: k[0])


def render(scene):
    sid = scene["id"]
    img = Image.open(B / "images" / f"{sid}_fixed.png").convert("RGB")
    iw, ih = img.size
    # Audio: lines back to back.
    t, starts, ends, parts = LEADS.get(sid, LEAD), [], [], []
    for i in range(len(scene["lines"])):
        data, rate = read_float(B / "voice" / f"{sid}_{i}.wav")
        starts.append(t); t += len(data) / rate; ends.append(t)
        parts.append((starts[-1], data)); t += GAP
    dur = max(MIN_DURS.get(sid, MIN_DUR), ends[-1] + TAIL)
    if scene.get("end_card"):
        dur = max(dur, ends[-1] + 1.4 + 2.0)  # reaction beat, then 2 s end card
    audio = np.zeros(int(dur * RATE) + 1, dtype=np.float32)
    for st, data in parts:
        i0 = int(st * RATE); audio[i0:i0 + len(data)] += data[: len(audio) - i0]
    if scene.get("lower_third"):
        audio[: len(STING)] += STING[: len(audio)]
    audio_path = B / "clips" / f"{sid}.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    import soundfile
    soundfile.write(str(audio_path), audio, RATE)

    keys = resolve(CAMERA[sid], starts, ends, dur)
    out = B / "clips" / f"{sid}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio_path),
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], stdin=subprocess.PIPE)
    base_w = iw  # zoom 1 shows the full image width
    for f in range(int(round(dur * FPS))):
        cx, cy, z = camera_at(keys, f / FPS)
        vw = base_w / z; vh = vw * H / W
        if vh > ih:  # never show beyond the image
            vh = ih; vw = vh * W / H
        x0 = min(max(cx * iw - vw / 2, 0), iw - vw); y0 = min(max(cy * ih - vh / 2, 0), ih - vh)
        s = vw / W
        frame = img.transform((W, H), Image.AFFINE, (s, 0, x0, 0, s, y0), resample=Image.BICUBIC)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close(); ff.wait()
    cues = [{"who": w, "text": tx, "start": round(a - 0.08, 2), "end": round(b + 0.25, 2)}
            for (w, tx), a, b in zip(scene["lines"], starts, ends)]
    (B / "cues").mkdir(exist_ok=True)
    (B / "cues" / f"{sid}.json").write_text(json.dumps(cues, indent=2, ensure_ascii=False))
    print(sid, f"{dur:.2f}s", flush=True)
    return round(dur, 2)


if __name__ == "__main__":
    durs = {s["id"]: render(s) for s in SCENES}
    (B / "durations.json").write_text(json.dumps(durs, indent=2))
    print("total", sum(durs.values()))
