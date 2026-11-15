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


TARGET = 40.0                # total reel length; pauses/holds scale evenly to hit it
REACTION, END_CARD = 1.4, 2.0
ROOM = {"scene1": (0.18, 0.05), "scene2": (0.35, 0.10), "scene3": (0.12, 0.04),
        "scene4": (0.35, 0.10), "scene5": (0.45, 0.12)}  # (reverb decay s, wet mix)


def voice_lengths(scene):
    return [read_float(B / "voice" / f"{scene['id']}_{i}.wav") for i in range(len(scene["lines"]))]


def layout(scene, lengths, k):
    """Line start/end times and scene length with every non-speech interval scaled by k."""
    sid = scene["id"]
    t, starts, ends = LEADS.get(sid, LEAD) * k, [], []
    for n in lengths:
        starts.append(t); t += n; ends.append(t); t += GAP * k
    dur = max(MIN_DURS.get(sid, MIN_DUR) * k, ends[-1] + TAIL * k)
    if scene.get("end_card"):
        dur = max(dur, ends[-1] + (REACTION + END_CARD) * k)
    return starts, ends, dur


def room(audio, sid):
    decay, wet = ROOM.get(sid, (0.2, 0.05))
    n = int(decay * RATE)
    ir = np.random.default_rng(7).normal(0, 1, n) * np.exp(-np.arange(n) / (decay * RATE / 6.9))
    ir[: int(0.012 * RATE)] = 0  # pre-delay
    rev = np.convolve(audio, ir / np.sqrt((ir ** 2).sum()), mode="full")[: len(audio)]
    return (audio * (1 - wet) + rev * wet * 0.6).astype(np.float32)


def render(scene, k, dur_override=None):
    sid = scene["id"]
    img = Image.open(B / "images" / f"{sid}_fixed.png").convert("RGB")
    iw, ih = img.size
    voices = voice_lengths(scene)
    starts, ends, dur = layout(scene, [len(d) / r for d, r in voices], k)
    dur = dur_override or dur
    audio = np.zeros(int(dur * RATE) + 1, dtype=np.float32)
    for st, (data, rate) in zip(starts, voices):
        i0 = int(st * RATE); audio[i0:i0 + len(data)] += data[: len(audio) - i0]
    audio = room(audio, sid)
    if scene.get("lower_third"):
        audio[: len(STING)] += STING[: len(audio)]
    audio_path = B / "clips" / f"{sid}.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    import soundfile
    soundfile.write(str(audio_path), audio, RATE)

    scaled = [[t * k if isinstance(t, (int, float)) else re.sub(r"([+-])([\d.]+)$", lambda m: f"{m.group(1)}{float(m.group(2)) * k:.3f}", t), *r]
              for t, *r in CAMERA[sid]]
    keys = resolve(scaled, starts, ends, dur)
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
    pad = min(0.25, GAP * k * 0.5)
    cues = [{"who": w, "text": tx, "start": round(max(0, a - 0.06), 2), "end": round(b + pad, 2)}
            for (w, tx), a, b in zip(scene["lines"], starts, ends)]
    (B / "cues").mkdir(exist_ok=True)
    (B / "cues" / f"{sid}.json").write_text(json.dumps(cues, indent=2, ensure_ascii=False))
    print(sid, f"{dur:.2f}s", flush=True)
    meta = {"duration": round(dur, 4)}
    if scene.get("context_at"):  # scene 5: box comes in once the camera has left the notice
        meta["context_at"] = round(starts[0] + 0.3 * k, 2)
    return meta


if __name__ == "__main__":
    lengths = {sc["id"]: [len(d) / r for d, r in voice_lengths(sc)] for sc in SCENES}
    total = lambda k: sum(layout(sc, lengths[sc["id"]], k)[2] for sc in SCENES)
    lo, hi = 0.3, 2.0
    for _ in range(60):  # total(k) is monotonic in k
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if total(mid) < TARGET else (lo, mid)
    k = (lo + hi) / 2
    # snap scene lengths to whole frames, putting any rounding remainder on the last scene
    durs = [round(layout(sc, lengths[sc["id"]], k)[2] * FPS) / FPS for sc in SCENES]
    durs[-1] = round(TARGET * FPS) / FPS - sum(durs[:-1])
    print(f"pause/hold scale k={k:.3f}", flush=True)
    meta = {sc["id"]: render(sc, k, d) for sc, d in zip(SCENES, durs)}
    (B / "durations.json").write_text(json.dumps(meta, indent=2))
    print("total", round(sum(m["duration"] for m in meta.values()), 3))
