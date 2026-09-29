"""Build the voiceover + SFX mix for "The East India Classroom Company" reel.

Voices are Kokoro neural TTS (British voices for the professor and judge).
Every sound effect is synthesized here with numpy/scipy, so no stock audio is needed.
Writes build/mix.wav and build/timeline.json (dialogue cues for the subtitles).

Needs: pip install kokoro-onnx soundfile numpy scipy, and the Kokoro model files
in models/ (see README.md).
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile
from kokoro_onnx import Kokoro
from scipy import signal

HERE = Path(__file__).parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "build"
SR = 48000
rng = np.random.default_rng(7)

PROF = ("bm_george", "en-gb")
JUDGE = ("bm_lewis", "en-gb")
STUDENT = ("af_heart", "en-us")
STUDENT2 = ("am_adam", "en-us")
WHISPER = ("am_puck", "en-us")

# Scene lengths (seconds). The script's 6 s slots for scenes 2 and 3 can't hold their
# dialogue at a natural pace, so they get ~1 s more, taken back from scene 4; the reel
# still lands under 40 s.
_LEN = [("announce", 5.0), ("climate", 7.1), ("laws", 7.1), ("trustee", 5.3),
        ("revolt", 4.0), ("verdict", 3.0), ("card", 8.0)]
SCENES, _t = [], 0.0
for _name, _d in _LEN:
    SCENES.append((_name, round(_t, 2), round(_t + _d, 2)))
    _t += _d
TOTAL = SCENES[-1][2]

# scene -> [(id, speaker label, voice, spoken text, subtitle, pause before)]
LINES = {
    "announce": [
        ("p1a", "PROF", PROF, "Good morning.", "Good morning.", 0.4),
        ("p1b", "PROF", PROF, "I am a despot.", "I am a despot.", 0.25),
        ("p1c", "PROF", PROF, "This class has no democracy.", "This class has no democracy.", 0.3),
    ],
    "climate": [
        ("s2", "STUDENT", STUDENT, "Sir, can we vote on the deadline?", "Sir, can we vote on the deadline?", 0.25),
        ("p2a", "PROF", PROF, "Impossible.", "Impossible.", 0.2),
        ("p2b", "PROF", PROF, "Nature has denied liberty to the torrid zone.",
         "Nature has denied liberty to the torrid zone.", 0.15),
        ("p2c", "PROF", PROF, "It's too hot for democracy.", "It's too hot for democracy.", 0.12),
    ],
    "laws": [
        ("s3", "STUDENT 2", STUDENT2, "But that's despotism!", "But that's despotism!", 0.3),
        ("p3a", "PROF", PROF, "Oriental despotism has no laws.", "Oriental despotism has no laws.", 0.2),
        ("p3b", "PROF", PROF, "My syllabus is unchanged, since remotest antiquity.",
         "My syllabus is unchanged since remotest antiquity.", 0.15),
    ],
    "trustee": [
        ("p4", "PROF", PROF, "Your prosperity, comes before any marks I take.",
         "Your prosperity comes before any marks I take.", 0.3),
        ("w4", "STUDENT (whispering)", WHISPER, "he's still taking marks.", "...he's still taking marks.", 0.45),
    ],
    "verdict": [
        ("j5", "JUDGE", JUDGE, "Acquitted.", "Acquitted.", 0.9),
    ],
}
CHANT = "Civilization from below! Impeach him! Impeach him!"


# ---------- helpers ----------
def secs(n):
    return np.arange(int(n * SR)) / SR


def trim(x, thresh=0.01):
    idx = np.where(np.abs(x) > thresh)[0]
    return x[max(0, idx[0] - 480):idx[-1] + 960] if len(idx) else x


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, "high", fs=SR, output="sos"), x)


def norm(x, peak=1.0):
    m = np.max(np.abs(x))
    return x * (peak / m) if m else x


def reverb(x, length=1.2, wet=0.25, bright=4000):
    t = secs(length)
    ir = lp(rng.standard_normal(len(t)), bright) * np.exp(-t * 6 / length)
    ir[0] = 0
    w = signal.fftconvolve(x, ir)[:len(x) + len(t)]
    out = np.zeros(len(w))
    out[:len(x)] = x
    return out + wet * norm(w, np.max(np.abs(x)) or 1)


def saw(freq_curve):
    """Band-limited-ish sawtooth from a per-sample frequency curve."""
    phase = np.cumsum(freq_curve) / SR
    return lp(2 * (phase % 1) - 1, 6000, 4)


def note(f):
    return 440 * 2 ** ((f - 69) / 12)


# ---------- sound effects ----------
def sting():
    """Dramatic orchestral hit: brass diminished chord + timpani + cymbal swell."""
    t = secs(2.4)
    brass = np.zeros(len(t))
    for m in (50, 53, 56, 62, 65):  # D F Ab D F — diminished, menacing
        f = note(m) * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t))
        brass += saw(np.full(len(t), 1.0) * f)
    env = np.minimum(t / 0.03, 1) * np.exp(-t * 1.4)
    brass = lp(brass * env, 2600) * 0.5
    timp = np.sin(2 * np.pi * np.cumsum(60 + 35 * np.exp(-t * 12)) / SR) * np.exp(-t * 2.2)
    timp += lp(rng.standard_normal(len(t)), 300) * np.exp(-t * 25) * 0.6
    cym = hp(rng.standard_normal(len(t)), 5000) * np.exp(-t * 2.5) * 0.12
    return reverb(norm(brass) * 0.8 + norm(timp) * 0.9 + cym, 1.8, 0.35)


def groan():
    """Crowd 'ughhh': a dozen formant-filtered voices sliding down in pitch."""
    t = secs(1.6)
    out = np.zeros(len(t))
    for _ in range(14):
        f0 = rng.choice([rng.uniform(100, 150), rng.uniform(190, 260)])
        start = rng.uniform(0, 0.15)
        glide = f0 * (1 - 0.22 * np.clip((t - start) / 1.3, 0, 1)) * (1 + 0.01 * np.sin(2 * np.pi * rng.uniform(4, 6) * t))
        v = saw(glide)
        v = bp(v, 500, 800) * 1.0 + bp(v, 950, 1250) * 0.6 + bp(v, 2300, 2700) * 0.15
        env = np.clip((t - start) / 0.18, 0, 1) * np.clip((1.55 - t) / 0.5, 0, 1)
        out += v * env * rng.uniform(0.6, 1)
    return reverb(norm(out), 0.6, 0.2)


def paper_unroll():
    """Flappy crinkly unrolling, slowing down as the scroll runs out."""
    t = secs(2.0)
    rate = 22 - 12 * t / 2.0
    flutter = 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(rate) / SR)
    hiss = bp(rng.standard_normal(len(t)), 1200, 7000) * flutter
    crackle = np.zeros(len(t))
    idx = rng.choice(len(t), 260, replace=False)
    crackle[idx] = rng.uniform(-1, 1, len(idx))
    crackle = bp(signal.lfilter([1], [1, -0.6], crackle), 2000, 9000)
    rumble = lp(rng.standard_normal(len(t)), 250) * flutter * 0.6
    env = np.minimum(t / 0.05, 1) * np.clip((2.0 - t) / 0.6, 0, 1)
    return norm((norm(hiss) * 0.6 + norm(crackle) * 0.9 + norm(rumble) * 0.4) * env)


def record_scratch(source):
    """Scrub a snippet of 'vinyl' back and forth with a wild speed curve."""
    t = secs(0.62)
    speed = np.interp(t, [0, 0.08, 0.2, 0.32, 0.45, 0.62], [1, 2.8, -3.2, 2.4, -1.5, 0])
    pos = 0.3 * SR + np.cumsum(speed)
    pos = np.clip(pos, 0, len(source) - 2)
    x = np.interp(pos, np.arange(len(source)), source)
    x += bp(rng.standard_normal(len(t)), 800, 4000) * np.abs(speed) * 0.08
    return norm(hp(x, 120) * np.minimum(t / 0.01, 1) * np.clip((0.62 - t) / 0.08, 0, 1))


def gavel():
    """Two wooden bangs in a courtroom."""
    out = np.zeros(int(1.6 * SR))
    for at, g in ((0.0, 1.0), (0.38, 0.9)):
        t = secs(0.5)
        knock = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
                    for f, a, d in ((170, 1.0, 22), (410, 0.7, 35), (960, 0.4, 60), (1900, 0.2, 90)))
        click = hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 400) * 0.8
        s = int(at * SR)
        out[s:s + len(t)] += (knock + click) * g
    return reverb(norm(out), 1.1, 0.35, 3000)


def brass_note(freq, dur, vib=0.0):
    t = secs(dur)
    f = freq * (1 + vib * np.sin(2 * np.pi * 6 * t) * np.clip(t / 0.15, 0, 1))
    x = saw(f)
    bright = lp(x, 900) * 0.5 + lp(x, 3500) * np.clip(t / 0.06, 0, 1) * 0.5
    env = np.minimum(t / 0.02, 1) * np.clip((dur - t) / 0.06, 0, 1)
    return bright * env


def fanfare():
    """Cheeky 'da-da-da-DAAA' trumpet."""
    seq = [(67, 0.11), (67, 0.11), (67, 0.11), (72, 0.75)]
    parts = [brass_note(note(m), d, 0.015 if d > 0.5 else 0) for m, d in seq]
    gap = np.zeros(int(0.03 * SR))
    x = np.concatenate([np.concatenate([p, gap]) for p in parts])
    return reverb(norm(x), 0.8, 0.2)


def pluck(freq, dur):
    """Harpsichord-ish pluck."""
    t = secs(dur)
    x = sum(np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (3 + 2.2 * k)) / k ** 0.8 for k in range(1, 9))
    return x * np.minimum(t / 0.003, 1)


def minuet(length):
    """Gentle baroque arpeggios in D minor: i - iv - V - i."""
    out = np.zeros(int(length * SR) + SR)
    chords = [(50, 53, 57, 62), (55, 58, 62, 67), (57, 61, 64, 69), (50, 53, 57, 62)]
    step, t = 0.25, 0.0
    i = 0
    while t < length:
        ch = chords[(i // 8) % 4]
        m = ch[[0, 1, 2, 3, 2, 1, 2, 3][i % 8]] + 12
        s = int(t * SR)
        p = pluck(note(m), 1.2) * 0.5
        if i % 8 == 0:
            p += pluck(note(ch[0] - 12), 1.2) * 0.6
        out[s:s + len(p)] += p[:len(out) - s]
        t += step
        i += 1
    return reverb(norm(out), 1.0, 0.2)[:int(length * SR)]


def crowd_bed(dur):
    t = secs(dur)
    x = bp(rng.standard_normal(len(t)), 250, 2500) * (0.7 + 0.3 * np.sin(2 * np.pi * 1.7 * t))
    return norm(x) * np.minimum(t / 0.3, 1) * np.clip((dur - t) / 0.5, 0, 1)


def whisperize(x):
    """Turn a voiced line into a breathy whisper: noise shaped by the speech envelope."""
    envl = lp(np.abs(x), 30)
    breath = bp(rng.standard_normal(len(x)), 1500, 6500) * envl * 3
    return norm(hp(x, 900) * 0.35 + breath)


# ---------- voices ----------
def resample(x, sr):
    return signal.resample_poly(x, SR, sr) if sr != SR else x


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    kokoro = Kokoro(str(HERE / "models/kokoro-v1.0.onnx"), str(HERE / "models/voices-v1.0.bin"))

    def say(text, voice, lang, speed=1.0):
        x, sr = kokoro.create(text, voice=voice, speed=speed, lang=lang)
        return trim(resample(np.asarray(x, dtype=float), sr))

    n = int(TOTAL * SR)
    mix = np.zeros((n, 2))

    def place(x, at, gain=1.0, pan=0.0):
        s = int(at * SR)
        e = min(n, s + len(x))
        mix[s:e, 0] += x[:e - s] * gain * (1 - max(0, pan))
        mix[s:e, 1] += x[:e - s] * gain * (1 + min(0, pan))

    # Per-speaker voice tracks, used to drive the cartoon mouths in sync with the audio.
    tracks = {k: np.zeros(n) for k in ("prof", "judge", "student", "student2", "whisper", "chant")}

    def track(key, x, at):
        s = int(at * SR)
        e = min(n, s + len(x))
        tracks[key][s:e] += x[:e - s]

    speaker = {"p": "prof", "j": "judge", "w": "whisper"}
    scene = {name: (s0, s1) for name, s0, s1 in SCENES}
    cues = []
    for name, lines in LINES.items():
        s0, s1 = scene[name]
        base = [0.95 if v[0] in (PROF[0], JUDGE[0]) else 1.0 for _, _, v, *_ in lines]
        clips = [say(text, v[0], v[1], sp) for (_, _, v, text, _, _), sp in zip(lines, base)]
        pauses = [ln[5] for ln in lines]
        room = (s1 - s0) - 0.3 - sum(pauses)
        need = sum(len(c) for c in clips) / SR
        f, orig = 1.0, base
        for _ in range(4):  # speed the whole scene up evenly until it fits (Kokoro keeps the pitch)
            if need <= room or f >= 1.4:
                break
            f = min(1.4, f * need / room * 1.01)
            base = [b * f for b in orig]
            clips = [say(text, v[0], v[1], sp) for (_, _, v, text, _, _), sp in zip(lines, base)]
            need = sum(len(c) for c in clips) / SR
        t = s0
        for (lid, who, _, _, sub, pause), x, sp in zip(lines, clips, base):
            t += pause
            if lid == "w4":
                x = whisperize(x)
            place(norm(x), t, {"w4": 0.55}.get(lid, 0.9), 0.25 if lid == "w4" else 0.0)
            track(speaker.get(lid[0], {"s2": "student", "s3": "student2"}.get(lid)), norm(x), t)
            cues.append({"id": lid, "scene": name, "who": who, "text": sub, "start": round(t, 3),
                         "end": round(t + len(x) / SR, 3), "speed": round(sp, 3)})
            print(f"{lid:4s} {t:6.2f}-{t + len(x) / SR:6.2f} (scene ends {s1}) speed {sp:.2f}")
            t += len(x) / SR

    # Chant: a crowd of voices, slightly out of sync and detuned.
    c0, c1 = scene["revolt"][0] + 0.25, scene["revolt"][1] - 0.2
    chant = np.zeros(int((c1 - c0 + 1) * SR))
    for v in ["am_adam", "am_michael", "af_bella", "af_sarah", "am_eric",
              "af_nicole", "bm_daniel", "bf_alice", "am_liam", "af_nova"]:
        lang = "en-gb" if v[0] == "b" else "en-us"
        x = say(CHANT, v, lang, 1.15)
        if len(x) / SR > c1 - c0 - 0.1:
            x = say(CHANT, v, lang, min(1.5, 1.15 * len(x) / SR / (c1 - c0 - 0.1)))
        x = signal.resample(x, int(len(x) * rng.uniform(0.97, 1.03)))
        s = int(rng.uniform(0, 0.06) * SR)
        e = min(len(chant), s + len(x))
        chant[s:e] += norm(x)[:e - s] * rng.uniform(0.6, 1.0)
    chant = reverb(norm(chant), 0.9, 0.3)
    place(norm(chant), c0, 0.8)
    track("chant", norm(chant), c0)
    place(crowd_bed(c1 - c0 + 0.4), c0 - 0.2, 0.18)
    cues.append({"id": "chant", "scene": "revolt", "who": "STUDENTS (chanting)",
                 "text": "Civilization from below! Impeach him!", "start": c0, "end": c1})

    # SFX, timed to the dialogue.
    cue = {c["id"]: c for c in cues}
    despot = cue["p1b"]
    sfx = {
        "sting": despot["start"] + 0.55 * (despot["end"] - despot["start"]),
        "groan": cue["p2c"]["end"] - 0.05,
        "paper": scene["laws"][0] + 0.05,
        "scratch": cue["w4"]["end"] - 0.15,
        "gavel": scene["verdict"][0] + 0.15,
        "fanfare": cue["j5"]["end"] + 0.15,
    }
    place(sting(), sfx["sting"], 0.75)
    place(groan(), sfx["groan"], 0.45)
    place(paper_unroll(), sfx["paper"], 0.55, 0.15)
    place(record_scratch(minuet(2.0)), sfx["scratch"], 0.6)
    place(gavel(), sfx["gavel"], 0.9)
    place(fanfare(), sfx["fanfare"], 0.5)

    # Soft baroque music under the explanation card, fading out.
    m0 = scene["card"][0]
    mus = minuet(TOTAL - m0)
    t = secs(len(mus) / SR)
    mus *= np.minimum(t / 0.8, 1) * np.clip((len(mus) / SR - t) / 4.0, 0, 1)
    place(mus, m0, 0.35)

    fps, hop = 30, SR // 30
    mouth = {}
    for k, x in tracks.items():
        frames = x[:len(x) // hop * hop].reshape(-1, hop)
        rms = np.sqrt((frames ** 2).mean(axis=1))
        ref = np.percentile(rms[rms > 0.01], 90) if (rms > 0.01).any() else 1
        mouth[k] = [round(float(v), 2) for v in np.clip(rms / ref, 0, 1)]

    mix = np.tanh(mix * 0.9) / np.tanh(0.9 * np.max(np.abs(mix)) or 1) * 0.95
    soundfile.write(str(OUT / "mix.wav"), mix, SR, subtype="PCM_16")
    (OUT / "timeline.json").write_text(json.dumps({"total": TOTAL, "scenes": SCENES, "cues": cues, "sfx": sfx, "fps": fps, "mouth": mouth}))
    print("sfx", {k: round(v, 2) for k, v in sfx.items()})


if __name__ == "__main__":
    main()
