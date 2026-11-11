"""Generate the music bed and sound effects, mix them with the voice stems, and
write the final audio, the subtitles and the muxed videos.

Usage: python3 mix.py <buildDir> <outDir>
Needs build/{timeline.json,events.json,narrator.wav,kamla.wav,video.mp4}.
Everything here is synthesized in code (numpy only): no samples, no stock audio.
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

BUILD = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else Path("out")
SR = 48000
BPM = 70
rng = np.random.default_rng(7)

TL = json.loads((BUILD / "timeline.json").read_text())
EV = json.loads((BUILD / "events.json").read_text())
SC = {s["id"]: s for s in TL["scenes"]}
CU = {c["id"]: c for c in TL["cues"]}
TOTAL = TL["total"]
N = int(TOTAL * SR)


def read_wav(path):
    with wave.open(str(path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    out = np.zeros(N, np.float32)
    out[:min(N, len(x))] = x[:N]
    return out


def write_wav(path, stereo):
    stereo = np.clip(stereo, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo.T.reshape(-1) * 32767).astype(np.int16).tobytes())


def band(x, lo=None, hi=None, slope=1.0):
    """Zero-phase FFT band filter with soft (Butterworth-like) edges."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (4 * slope))
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** (4 * slope))
    return np.fft.irfft(np.fft.rfft(x) * g, n).astype(np.float32)


def convolve(x, ir):
    n = len(x) + len(ir) - 1
    m = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)].astype(np.float32)


def automation(points):
    """Piecewise-linear envelope from (time, value) points."""
    pts = sorted(points)
    t = np.arange(N) / SR
    return np.interp(t, [p[0] for p in pts], [p[1] for p in pts]).astype(np.float32)


def env_follow(x, win=0.25):
    k = int(win * SR)
    e = np.sqrt(np.convolve(x ** 2, np.ones(k) / k, mode="same"))
    return np.clip(e / (e.max() + 1e-9) * 3, 0, 1).astype(np.float32)


T = lambda s: np.arange(int(s * SR)) / SR


# ---------------------------------------------------------------- sound effects
def sfx_beep(f=1000, d=.42):
    t = T(d)
    return (.32 * np.sin(2 * np.pi * f * t) * np.clip(t / .006, 0, 1) * np.clip((d - t) / .01, 0, 1)).astype(np.float32)


def sfx_key(v=.5):
    d = .09
    t = T(d)
    click = band(rng.standard_normal(len(t)).astype(np.float32), 1800, 7000) * np.exp(-t / .004)
    body = np.sin(2 * np.pi * (180 + 80 * v) * t) * np.exp(-t / .018)
    clack = np.sin(2 * np.pi * (2400 + 900 * v) * t) * np.exp(-t / .006)
    return (.5 * click + .35 * body + .15 * clack).astype(np.float32) * (.8 + .4 * v)


def sfx_stamp():
    d = .7
    t = T(d)
    f = 45 + 40 * np.exp(-t / .04)
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .16)
    slap = band(rng.standard_normal(len(t)).astype(np.float32), 150, 2500) * np.exp(-t / .025)
    knock = np.sin(2 * np.pi * 210 * t) * np.exp(-t / .05)
    return (.9 * thump + .45 * slap + .3 * knock).astype(np.float32)


def sfx_slide(d=.55):
    t = T(d)
    nz = band(rng.standard_normal(len(t)).astype(np.float32), 1500, 6500)
    envl = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    return (.22 * nz * envl).astype(np.float32)


def sfx_pin():
    t = T(.25)
    return (.5 * np.sin(2 * np.pi * 110 * t) * np.exp(-t / .045)
            + .25 * band(rng.standard_normal(len(t)).astype(np.float32), 300, 3000) * np.exp(-t / .01)).astype(np.float32)


def sfx_thud():
    t = T(1.0)
    def hit(a, delay, dec):
        tt = np.clip(t - delay, 0, None)
        f = 42 + 22 * np.exp(-tt / .05)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / dec) * (t >= delay)
        return a * s
    return (hit(1.0, 0, .2) + hit(.6, .28, .17)).astype(np.float32)


def sfx_tick(v=1.0):
    t = T(.06)
    nz = band(rng.standard_normal(len(t)).astype(np.float32), 2000, 9000) * np.exp(-t / .003)
    ring = np.sin(2 * np.pi * 3100 * t) * np.exp(-t / .008)
    return (.45 * nz + .25 * ring).astype(np.float32) * v


def sfx_glow():
    t = T(1.6)
    return (.06 * (np.sin(2 * np.pi * 659.3 * t) + .5 * np.sin(2 * np.pi * 988 * t)) * np.exp(-t / .5)
            * np.clip(t / .02, 0, 1)).astype(np.float32)


def sfx_hangup():
    t = T(.35)
    clk = band(rng.standard_normal(len(t)).astype(np.float32), 200, 4000) * np.exp(-t / .012)
    return (.5 * clk + .2 * np.sin(2 * np.pi * 90 * t) * np.exp(-t / .04)).astype(np.float32)


def sfx_lamp():
    t = T(.12)
    return (.35 * band(rng.standard_normal(len(t)).astype(np.float32), 800, 6000) * np.exp(-t / .006)).astype(np.float32)


def place(bus, x, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or i + len(x) <= 0:
        return
    seg = x[: max(0, min(len(x), N - i))] * gain
    bus[0, i:i + len(seg)] += seg * np.sqrt(.5 - pan / 2) * 1.414
    bus[1, i:i + len(seg)] += seg * np.sqrt(.5 + pan / 2) * 1.414


def phone(x):
    """Voicemail / phone-line colour: band-limit, a little grit."""
    y = band(x, 320, 3300, 1.5)
    y = np.tanh(y * 2.2) / np.tanh(2.2)
    return y.astype(np.float32)


# ---------------------------------------------------------------- music
def music():
    t = np.arange(N) / SR
    beat = 60 / BPM
    chords = [[73.42, 110.0, 174.61, 261.63, 329.63],   # Dm(add9)
              [58.27, 116.54, 174.61, 233.08, 293.66]]  # Bb/D-ish
    bar16 = 16 * beat

    def layer(nharm, rolloff):
        out = np.zeros((2, N), np.float32)
        for ci, notes in enumerate(chords):
            # crossfade weight for this chord: smooth alternation every 16 beats
            x = (.5 - .5 * np.cos(np.pi * ((t / bar16) % 2))).astype(np.float32)
            w = x if ci else 1 - x
            for ni, f0 in enumerate(notes):
                for side, det in ((0, .9985), (1, 1.0015)):
                    s = np.zeros(N, np.float32)
                    for h in range(1, nharm + 1):
                        s += np.sin(2 * np.pi * f0 * det * h * t + rng.uniform(0, 6.28)).astype(np.float32) / h ** rolloff
                    lfo = .65 + .35 * np.sin(2 * np.pi * (.05 + .013 * ni) * t + ni + side)
                    out[side] += s * lfo * w / len(notes)
        return out

    dark = layer(3, 1.6)
    bright = layer(8, 1.1)
    bright[0] = band(bright[0], 120, 3200)
    bright[1] = band(bright[1], 120, 3200)
    dark[0] = band(dark[0], 40, 900)
    dark[1] = band(dark[1], 40, 900)

    # 70 BPM pulse: soft low heartbeat-ish hit on every beat (+ offbeats when tense)
    pulse = np.zeros(N, np.float32)
    off = np.zeros(N, np.float32)
    hit_t = T(.6)
    hit = (np.sin(2 * np.pi * np.cumsum(48 + 30 * np.exp(-hit_t / .03)) / SR) * np.exp(-hit_t / .22)).astype(np.float32)
    k = 0
    while k * beat < TOTAL:
        i = int(k * beat * SR)
        seg = hit[: max(0, min(len(hit), N - i))]
        pulse[i:i + len(seg)] += seg
        j = int((k + .5) * beat * SR)
        seg = hit[: max(0, min(len(hit), N - j))] * .5
        off[j:j + len(seg)] += seg
        k += 1

    # rising shimmer for scene 7: filtered noise + slowly rising tone
    rise = band(rng.standard_normal(N).astype(np.float32), 2500, 7000) * .25
    p7 = SC["people"]
    rp = np.clip((t - p7["start"]) / (SC["clock"]["end"] - p7["start"]), 0, 1)
    tone = np.sin(2 * np.pi * np.cumsum(220 + 220 * rp ** 2) / SR).astype(np.float32) * .1

    s1, s2, s3, s4, s5, s6, s7, s8 = (SC[k] for k in ["title", "kabir", "hospital", "rahul", "question", "people", "clock", "end"])
    miracle = CU["s4p3l2"]["end"]
    died = CU["s5p4l1"]
    cut = s7["end"]
    pad = automation([(0, 0), (s1["start"] + .2, 0), (s1["start"] + 3.0, .55), (miracle, .55), (miracle + .35, .18),
                      (miracle + 1.6, .2), (s3["end"], .4), (died["start"], .38), (died["end"] - .2, 0),
                      (s5["start"], 0), (s5["start"] + 2.5, .42), (s6["start"], .45), (s6["end"], 1.0),
                      (cut - .001, 1.0), (cut, 0), (TOTAL, 0)])
    brt = automation([(0, 0), (s6["start"], .1), (s6["end"], 1.0), (cut - .001, 1.0), (cut, 0), (TOTAL, 0)])
    pls = automation([(0, 0), (s2["start"], 0), (s2["start"] + 2, .5), (s3["end"] - 2, .45), (s4["start"], 0),
                      (s5["start"], 0), (s5["start"] + 3, .3), (s6["start"], .45), (s6["end"], 1.0),
                      (cut - .001, .9), (cut, 0), (TOTAL, 0)])
    offl = automation([(0, 0), (s6["start"] + (s6["end"] - s6["start"]) * .5, 0), (s6["end"], .8), (cut - .001, .8), (cut, 0), (TOTAL, 0)])
    rsl = automation([(0, 0), (s6["start"], 0), (s7["end"] - .001, 1.0), (cut, 0), (TOTAL, 0)])

    mus = np.zeros((2, N), np.float32)
    mus += dark * pad * .55 + bright * brt * pad * .35
    mono = pulse * pls * .55 + off * offl * .3 + (rise * rsl * .5 + tone * rsl)
    mus += mono
    return mus


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    narr = read_wav(BUILD / "narrator.wav")
    kamla = read_wav(BUILD / "kamla.wav")

    # narrator: gentle low cut + a small dry room
    narr = band(narr, 75, 11000)
    ir_t = T(.35)
    ir = (rng.standard_normal(len(ir_t)) * np.exp(-ir_t / .07)).astype(np.float32) * .05
    ir[0] = 1.0
    narr = convolve(narr, ir)
    narr /= np.abs(narr).max() + 1e-9
    narr *= .82

    kamla_phone = phone(kamla)
    kamla_phone /= np.abs(kamla_phone).max() + 1e-9
    kamla_phone *= .8

    sfx = np.zeros((2, N), np.float32)
    hiss_on = hiss_off = None
    replay = None
    cut = None
    for e in EV:
        k, t, vol = e["kind"], e["t"], e.get("vol", 1.0)
        if k == "key":
            place(sfx, sfx_key(e.get("v", .5)), t, .32 * vol, (e.get("v", .5) - .5) * .4)
        elif k == "beep":
            place(sfx, phone(np.pad(sfx_beep(1000), (0, 2000))), t, .9)
        elif k == "beep2":
            place(sfx, phone(np.pad(sfx_beep(1000, .3), (0, 2000))), t, .8)
        elif k == "hangup":
            place(sfx, sfx_hangup(), t, .9)
        elif k == "hiss_on":
            hiss_on = t
        elif k == "hiss_off":
            hiss_off = t
        elif k in ("stamp", "datestamp"):
            place(sfx, sfx_stamp(), t, .95 * vol)
            if k == "datestamp":
                place(sfx, sfx_tick(1.2), t - .02, .9)
        elif k == "slide":
            place(sfx, sfx_slide(), t, vol, .2)
        elif k == "pin":
            place(sfx, sfx_pin(), t, .9, (rng.random() - .5) * .6)
        elif k == "thud":
            place(sfx, sfx_thud(), t, .95 * vol)
        elif k == "tick":
            place(sfx, sfx_tick(), t, .7 * vol, .1)
        elif k == "glow":
            place(sfx, sfx_glow(), t, 1.0)
        elif k == "lamp":
            place(sfx, sfx_lamp(), t, .8)
        elif k == "replay_on":
            replay = [t, e["src"], e["len"], None]
        elif k == "replay_off" and replay:
            replay[3] = t
        elif k == "cut":
            cut = t

    # tape hiss under the voicemail
    if hiss_on is not None:
        a, b = int(hiss_on * SR), int(hiss_off * SR)
        h = band(rng.standard_normal(b - a).astype(np.float32), 900, 9000) * .035
        h *= np.clip(np.arange(b - a) / (.08 * SR), 0, 1)
        sfx[:, a:b] += h

    # the voicemail replaying faintly while Kabir listens again
    voice_bus = narr.copy()
    if replay:
        t0, src, ln, t1 = replay
        a, n = int(t0 * SR), int(((t1 or t0 + ln) + 1.5 - t0) * SR)
        loop = kamla_phone[int(src * SR): int((src + ln) * SR)]
        seg = np.resize(loop, n)
        fade = np.clip(1 - (np.arange(n) / SR - ((t1 or t0 + ln) - t0)) / 1.5, 0, 1) * np.clip(np.arange(n) / (.4 * SR), 0, 1)
        seg = band(seg, 400, 2600) * fade * .2
        sfx[:, a:a + n] += seg[: max(0, min(n, N - a))]

    voice_bus += kamla_phone

    mus = music()
    # duck the music under the narrator
    duck = 1 - .5 * env_follow(narr, .4)
    mus *= duck

    mix = mus * .5 + sfx * .8 + voice_bus[None, :] * 1.0
    if cut is not None:  # hard cut to silence at the end of the clock scene
        a = int(cut * SR)
        b = int(SC["end"]["start"] * SR + .5 * SR)
        mix[:, a:b] = 0
    mix /= np.abs(mix).max() + 1e-9
    mix *= .9
    write_wav(BUILD / "mix.wav", mix)
    print("mixed audio")

    write_srt(OUT / "grace_loan_opening.srt", TL["cues"])
    write_srt(BUILD / "narration_only.srt", [c for c in TL["cues"] if c["speaker"] == "NARRATOR"])

    if "--audio-only" in sys.argv:
        return
    mp4 = OUT / "grace_loan_opening.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", str(BUILD / "video.mp4"), "-i", str(BUILD / "mix.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=14", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", "-shortest", str(mp4)], check=True, stderr=subprocess.DEVNULL)
    print("wrote", mp4)
    style = ("FontName=Inter,FontSize=15,PrimaryColour=&H00D6E6ED,OutlineColour=&H00000000,BackColour=&HA0000000,"
             "BorderStyle=4,Outline=0,Shadow=0,MarginV=22")
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-vf",
                    f"subtitles={BUILD / 'narration_only.srt'}:force_style='{style}'",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-movflags", "+faststart", str(OUT / "grace_loan_opening_captioned.mp4")],
                   check=True, stderr=subprocess.DEVNULL)
    print("wrote", OUT / "grace_loan_opening_captioned.mp4")


def split_caption(text, start, end, maxlen=84):
    if len(text) <= maxlen:
        return [(text, start, end)]
    mid = len(text) // 2
    cands = [i for i, ch in enumerate(text) if ch in ",;:—" and 20 < i < len(text) - 20] or \
            [i for i, ch in enumerate(text) if ch == " "]
    i = min(cands, key=lambda j: abs(j - mid)) + 1
    a, b = text[:i].strip(), text[i:].strip()
    tm = start + (end - start) * len(a) / (len(a) + len(b))
    return split_caption(a, start, tm, maxlen) + split_caption(b, tm, end, maxlen)


def wrap(text, width=46):
    if len(text) <= width:
        return text
    mid = len(text) // 2
    spaces = [i for i, ch in enumerate(text) if ch == " "]
    i = min(spaces, key=lambda j: abs(j - mid))
    return text[:i] + "\n" + text[i + 1:]


def ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(path, cues):
    items = []
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else c["end"] + 2
        end = min(c["end"] + .35, nxt - .05)
        for text, a, b in split_caption(c["text"], c["start"], end):
            items.append((a, b, text))
    lines = []
    for n, (a, b, text) in enumerate(items, 1):
        lines += [str(n), f"{ts(a)} --> {ts(b)}", wrap(text), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
