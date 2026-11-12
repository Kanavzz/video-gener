"""Build the voice + SFX + music mix and the timeline for the Grace Loan opening.

Voices come from Microsoft Edge neural TTS (`pip install edge-tts`, no key needed):
  NARRATOR      en-IN-PrabhatNeural (Indian-English male, calm, low)
  KAMLA SINGH   hi-IN-SwaraNeural   (Hindi female, slowed, lowered, trembling)
Set NO_TTS=1 to skip synthesis: the timeline then uses estimated gaps and the
video is silent apart from SFX/music, so the lines can be recorded later.

Writes into <out dir> (default build/):
  timeline.json, mix.wav, grace_loan_opening.srt, voiceover_lines.txt
Requires ffmpeg and numpy.
"""
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "build"
CACHE = HERE / "build" / "tts-cache"
SR = 48000
NO_TTS = os.environ.get("NO_TTS") == "1"

VOICES = {
    "NARRATOR": dict(voice="en-IN-PrabhatNeural", rate="+20%", pitch="-7Hz"),
    "KAMLA": dict(voice="hi-IN-SwaraNeural", rate="-8%", pitch="-9Hz"),
}
SPEAKER_NAME = {"NARRATOR": "NARRATOR", "KAMLA": "SMT. KAMLA SINGH"}

# ---------------------------------------------------------------- script ----
# Each line: (speaker, spoken text for TTS, subtitle text, romanised original or None)
KAMLA_LINES = [
    ("आपने मेरे राहुल को मार दिया…", "You killed my Rahul…", "Aapne mere Rahul ko maar diya…"),
    ("वो खून की खांसी कर रहा था, और आपने उसे बिना इलाज के घर भेज दिया।",
     "He was coughing blood, and you sent him home without treating him.",
     "Woh khoon ki khaansi kar raha tha, aur aapne usse bina ilaaj ke ghar bhej diya."),
    ("दो दिन… सिर्फ़ दो दिन।", "Two days… only two days.", "Do din… sirf do din."),
    ("सिंह परिवार आपको कभी माफ़ नहीं करेगा।", "The Singh family will never forgive you.",
     "Singh parivaar aapko kabhi maaf nahi karega."),
]

NARRATION = {
    3: [
        "Kabir Rao believes hospitals exist for people who cannot pay.",
        "That is why he chose Grace Loan Memorial Hospital — famous across Dehradun for free treatment, "
        "and one of the few private hospitals on the government's State Pro Bono Care Scheme.",
        "Five months in, his work is filing, data entry and errands.",
        "On Monday, the thirtieth of November, he is handed one more dull job: "
        "clear out a month of old voicemails from the hospital's line.",
        "He has no idea it will put him in the middle of the biggest scandal the hospital has ever hidden.",
    ],
    4: [
        "From the outside, Grace Loan is everything Kabir hoped for.",
        "A two-hundred-and-ten-bed hospital on Rajpur Road.",
        "A motto of 'healing without barriers'.",
        "A Director who says no patient is ever turned away for want of money.",
        "The government pays the hospital a fixed amount for every poor patient it treats — "
        "and its website boasts of hundreds of free treatments.",
        "But a twelve-year-old boy named Rahul came here for help…",
        "and two days later, he was dead.",
    ],
    5: [
        "Now, you are Kabir Rao.",
        "You have one and a half hours to crack the case — to find out what is really happening "
        "to the pro bono patients, and who is behind it.",
        "Follow the clues.",
        "Answer every question in the Google Form.",
        "Your investigation begins… now.",
    ],
}
# Spoken form when it differs from the written line (helps the TTS voice).
SPOKEN_FIX = {
    "A two-hundred-and-ten-bed hospital on Rajpur Road.": "A two hundred and ten bed hospital, on Rajpur Road.",
    "But a twelve-year-old boy named Rahul came here for help…": "But a twelve year old boy named Rahul, came here for help...",
    "and two days later, he was dead.": "and two days later... he was dead.",
    "Your investigation begins… now.": "Your investigation begins... now.",
}

# Visual typing blocks (text, chars per second) – the HTML reads these from the timeline.
S1_LINES = ["GRACE LOAN MEMORIAL HOSPITAL — GENERAL LINE", "PLAYING MESSAGE 31 OF 47",
            "RECEIVED: TUE 24 NOV 2026 · 11:52 PM"]
TITLE = "THE GRACE LOAN MEMORIAL CASE"
S5_TYPED = [
    "You are Kabir Rao.",
    "You have 1.5 hours to crack the case.",
    "Find out what is really happening to the pro bono patients —",
    "and who is behind it.",
]
S5_FINAL = ["Follow the clues.", "Answer in the Google Form.", "Your investigation begins now."]


# ----------------------------------------------------------------- utils ----
def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
    return data


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if data.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


async def _tts(text, cfg, mp3):
    import certifi
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):  # sandbox proxy CA
        certifi.where = lambda: ca
    import edge_tts
    words = []
    com = edge_tts.Communicate(text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"], boundary="WordBoundary")
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"w": chunk["text"], "t": chunk["offset"] / 1e7, "d": chunk["duration"] / 1e7})
    return words


VOICE_FX = {
    # Clean, present narrator: rumble cut, gentle compression, a touch of presence.
    "NARRATOR": "highpass=f=70,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=120,"
                "equalizer=f=3000:t=q:w=1.2:g=2.5",
    # Voicemail: band-limited (still intelligible), trembling pitch + amplitude.
    "KAMLA": "highpass=f=180,lowpass=f=6500,vibrato=f=5.5:d=0.10,tremolo=f=4.5:d=0.18,"
             "acompressor=threshold=-22dB:ratio=3:attack=5:release=100,equalizer=f=2500:t=q:w=1.5:g=3",
}


def synth(speaker, text):
    """Return (samples, words) for a processed, loudness-normalised line."""
    cfg = VOICES[speaker]
    key = hashlib.sha1(json.dumps([speaker, text, cfg, VOICE_FX[speaker]]).encode()).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    mp3, wav, meta = CACHE / f"{key}.mp3", CACHE / f"{key}.wav", CACHE / f"{key}.json"
    if not wav.exists():
        words = asyncio.run(_tts(text, cfg, mp3))
        run("ffmpeg", "-y", "-i", str(mp3), "-af",
            VOICE_FX[speaker] + ",loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000",
            "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", str(wav))
        meta.write_text(json.dumps(words))
    data = read_wav(wav)
    # Trim leading/trailing silence so gaps are under our control; shift words to match.
    thr = 0.01
    idx = np.where(np.abs(data) > thr)[0]
    a, b = (max(0, idx[0] - int(0.03 * SR)), min(len(data), idx[-1] + int(0.08 * SR))) if len(idx) else (0, len(data))
    words = json.loads(meta.read_text())
    for w in words:
        w["t"] = round(w["t"] - a / SR, 3)
    return data[a:b], words


def estimate(text):  # NO_TTS fallback: ~2.6 words / s
    n = len(text.split())
    return np.zeros(int(SR * n / 2.6), dtype=np.float32), []


# ------------------------------------------------------------------- SFX ----
rng = np.random.default_rng(7)


def env(n, attack, release):
    e = np.ones(n, dtype=np.float32)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def tone(freq, dur, amp):
    t = np.arange(int(dur * SR)) / SR
    return (amp * np.sin(2 * np.pi * freq * t) * env(len(t), 0.006, 0.02)).astype(np.float32)


def phone_beep():
    return tone(1000, 0.42, 0.45) + tone(2000, 0.42, 0.05)


def end_beep():
    return tone(620, 0.6, 0.45) + tone(1240, 0.6, 0.04)


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # short buffers only
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def fft_filter(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        m *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x)).astype(np.float32)


def hiss(dur):
    n = int(dur * SR)
    x = fft_filter(rng.standard_normal(n).astype(np.float32), lo=1500, hi=9000) * 0.035
    crackle = (rng.random(n) > 0.9993) * rng.standard_normal(n) * 0.08
    x += fft_filter(crackle.astype(np.float32), lo=800)
    return x * env(n, 0.15, 0.03)


def key_click(strength=1.0, space=False):
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n).astype(np.float32) * np.exp(-t / 0.004)
    body = np.sin(2 * np.pi * (180 if space else rng.uniform(1700, 2600)) * t) * np.exp(-t / 0.012)
    thunk = np.sin(2 * np.pi * 110 * t) * np.exp(-t / 0.02)
    return (0.22 * noise + 0.18 * body + 0.18 * thunk).astype(np.float32) * strength


def stamp():
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    f = 55 + 70 * np.exp(-t / 0.04)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16)
    slap = fft_filter(rng.standard_normal(n).astype(np.float32), hi=2500) * np.exp(-t / 0.018)
    return (0.85 * boom + 0.55 * slap).astype(np.float32)


def tick(hi=True):
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    return (0.32 * np.sin(2 * np.pi * (3200 if hi else 2500) * t) * np.exp(-t / 0.006)
            + 0.15 * rng.standard_normal(n) * np.exp(-t / 0.002)).astype(np.float32)


def breath(dur=0.45):  # shaky inhale between sobbed phrases
    n = int(dur * SR)
    x = fft_filter(rng.standard_normal(n).astype(np.float32), lo=600, hi=4000)
    t = np.linspace(0, 1, n)
    shape = np.sin(np.pi * t) ** 1.5 * (1 + 0.35 * np.sin(2 * np.pi * 9 * t))
    return (x * shape * 0.06).astype(np.float32)


def pad(dur):
    """Low tense ambient pad in D minor with a slow cluster swell (stereo)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2), dtype=np.float32)
    notes = [(36.71, 1.0), (73.42, 0.8), (110.0, 0.45), (146.83, 0.3), (174.61, 0.22), (155.56, 0.10)]
    for k, (f0, a) in enumerate(notes):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * t / (11 + 3 * k) + k)
        for ch, det in ((0, 0.998), (1, 1.002)):
            s = np.zeros(n, dtype=np.float32)
            for h in range(1, 5):
                s += np.sin(2 * np.pi * f0 * det * h * t + h * k) / h ** 1.6
            out[:, ch] += a * lfo * s
    # slow heartbeat-like sub pulse every 1.5 s
    beat = np.zeros(n, dtype=np.float32)
    bl = int(0.35 * SR)
    bt = np.arange(bl) / SR
    thump = np.sin(2 * np.pi * (48 + 30 * np.exp(-bt / 0.03)) * bt) * np.exp(-bt / 0.09)
    for st in np.arange(0.5, dur - 0.4, 1.5):
        i = int(st * SR)
        beat[i:i + bl] += thump[: n - i]
    out += 0.9 * beat[:, None]
    out /= np.abs(out).max()
    return out


# -------------------------------------------------------------- timeline ----
def subtitle_chunks(text, words, start, max_words=11):
    """Split a narration sentence into subtitle cues using word timings."""
    if not words:
        return [{"start": start, "end": None, "text": text}]
    tokens = text.split()
    # Map word-boundary events onto the written tokens in order (punctuation lives in tokens).
    times, wi = [], 0
    for tok in tokens:
        core = re.sub(r"[^\w']", "", tok).lower()
        if not core:
            times.append(times[-1] if times else (words[0]["t"], words[0]["d"]))
            continue
        while wi < len(words) - 1 and re.sub(r"[^\w']", "", words[wi]["w"]).lower()[:3] != core[:3] \
                and core[:3] not in re.sub(r"[^\w']", "", words[wi]["w"]).lower():
            wi += 1
        times.append((words[min(wi, len(words) - 1)]["t"], words[min(wi, len(words) - 1)]["d"]))
        wi = min(wi + 1, len(words) - 1)
    chunks, cur = [], []
    for i, tok in enumerate(tokens):
        cur.append(i)
        brk = tok.endswith((",", ":", "—", ";", "…", ".")) or (i + 1 < len(tokens) and tokens[i + 1] == "—")
        if (len(cur) >= max_words) or (brk and len(cur) >= 5) or i == len(tokens) - 1:
            chunks.append(cur)
            cur = []
    if len(chunks) > 1 and len(chunks[-1]) < 3:
        chunks[-2] += chunks.pop()
    cues = []
    for c in chunks:
        s = start + times[c[0]][0]
        e = start + times[c[-1]][0] + times[c[-1]][1]
        cues.append({"start": round(s, 3), "end": round(e + 0.15, 3),
                     "text": " ".join(tokens[i] for i in c)})
    return cues


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    say = estimate if NO_TTS else (lambda spk, txt: synth(spk, txt))

    voice_items = []   # (start, samples)
    cues = []          # subtitles
    sfx = []           # (start, samples, gain)
    events = {}        # named times for the visuals
    typing = []        # visual typing blocks
    scenes = []

    def type_block(name, text, start, cps, gain=0.55):
        typing.append({"id": name, "text": text, "start": round(start, 3), "cps": cps})
        for i, ch in enumerate(text):
            if ch != " " or i % 2 == 0:
                sfx.append((start + i / cps + rng.uniform(-0.01, 0.01),
                            key_click(rng.uniform(0.7, 1.0), ch == " "), gain))
        return start + len(text) / cps

    # ---- Scene 1: voicemail ----
    t0 = 0.0
    t = t0 + 0.6
    for i, line in enumerate(S1_LINES):
        t = type_block(f"s1_{i}", line, t, 50, gain=0.35) + 0.1
    events["beep1"] = t + 0.1
    sfx.append((events["beep1"], phone_beep(), 1.0))
    t = events["beep1"] + 0.85
    events["vm_start"] = t
    for i, (hi_txt, en_txt, _) in enumerate(KAMLA_LINES):
        data, words = say("KAMLA", hi_txt)
        voice_items.append((t, data, 1.0))
        d = len(data) / SR
        cues.append({"start": round(t, 3), "end": round(t + d + 0.2, 3), "text": en_txt, "speaker": "KAMLA"})
        t += d
        if i < len(KAMLA_LINES) - 1:
            sfx.append((t + 0.12, breath(), 1.0))
            t += 0.6
    events["vm_end"] = t
    sfx.append((events["vm_start"] - 0.6, hiss(t - events["vm_start"] + 0.9), 1.0))
    events["dead"] = t + 0.35
    events["beep2"] = events["dead"] + 0.15
    sfx.append((events["beep2"], end_beep(), 1.0))
    s1_end = events["beep2"] + 0.6 + 1.0
    scenes.append({"id": 1, "start": t0, "end": round(s1_end, 3)})

    # ---- Scene 2: title ----
    t0 = s1_end
    title_end = type_block("title", TITLE, t0 + 0.4, 17, gain=0.6)
    events["stamp_title"] = title_end + 0.45
    sfx.append((events["stamp_title"], stamp(), 1.0))
    events["music_in"] = events["stamp_title"]
    s2_end = events["stamp_title"] + 2.0
    scenes.append({"id": 2, "start": round(t0, 3), "end": round(s2_end, 3)})

    # ---- Scenes 3-5: narration ----
    t0 = s2_end
    for sc in (3, 4, 5):
        t = t0 + (0.6 if sc != 5 else 1.3)
        sentences = []
        for j, line in enumerate(NARRATION[sc]):
            spoken = SPOKEN_FIX.get(line, line)
            data, words = say("NARRATOR", spoken)
            voice_items.append((t, data, 1.0))
            d = len(data) / SR
            for c in subtitle_chunks(line, words, t):
                c["speaker"] = "NARRATOR"
                if c["end"] is None:
                    c["end"] = round(t + d, 3)
                cues.append(c)
            sentences.append({"start": round(t, 3), "end": round(t + d, 3)})
            if sc == 4 and line.startswith("and two days"):
                dw = [w for w in words if w["w"].lower().startswith("dead")]
                events["dead_word"] = round(t + (dw[0]["t"] if dw else d - 0.4), 3)
            if sc == 5 and line.startswith("Your investigation"):
                nw = [w for w in words if w["w"].lower().startswith("now")]
                events["now_word"] = round(t + (nw[0]["t"] if nw else d - 0.4), 3)
            t += d
            # breathing room between sentences; extra beats where the script asks
            gap = 0.35
            if sc == 4 and line.startswith("But a twelve"):
                gap = 0.7
            if sc == 5 and j == 1:
                gap = 0.9  # let the clock appear
            if j < len(NARRATION[sc]) - 1:
                t += gap
        events[f"s{sc}_sentences"] = sentences
        tail = {3: 0.8, 4: 1.0, 5: 0.0}[sc]
        if sc == 5:
            events["cut_black"] = round(events["now_word"] + 0.55, 3)
            end = events["cut_black"] + 2.6  # 2 s+ end card hold
            events["clock_start"] = sentences[1]["end"] + 0.1
            for k in range(int((events["now_word"] - events["clock_start"]) / 1.0) + 1):
                tt = events["clock_start"] + k
                if tt < events["now_word"] - 0.1:
                    sfx.append((tt, tick(k % 2 == 0), 0.8))
            sfx.append((events["now_word"] + 0.05, stamp(), 1.15))
        else:
            end = t + tail
        scenes.append({"id": sc, "start": round(t0, 3), "end": round(end, 3)})
        t0 = end

    total = scenes[-1]["end"]
    n = int(total * SR) + SR

    # ---- typed lines for scene 5 (visual only, synced to narration) ----
    s5 = events["s5_sentences"]
    events["s5_type"] = [s5[0]["start"], s5[1]["start"], s5[1]["start"] + 1.6, s5[1]["end"] - 1.0]
    events["s5_final"] = [s5[2]["start"], s5[3]["start"], s5[4]["start"]]

    # ---- mix ----
    voice = np.zeros(n, dtype=np.float32)
    for st, data, g in voice_items:
        i = int(st * SR)
        voice[i:i + len(data)] += data * g
    fx = np.zeros(n, dtype=np.float32)
    for st, data, g in sfx:
        i = max(0, int(st * SR))
        m = min(len(data), n - i)
        fx[i:i + m] += data[:m] * g

    # music: starts at title stamp, ducks under voice, dips to silence on "dead", stops on "now"
    m_start = events["music_in"]
    music = np.zeros((n, 2), dtype=np.float32)
    p = pad(total - m_start + 1)
    i0 = int(m_start * SR)
    music[i0:i0 + len(p)] = p[: n - i0]
    gain = np.full(n, 0.11, dtype=np.float32)
    gain[: i0 + int(1.5 * SR)] *= np.clip((np.arange(i0 + int(1.5 * SR)) - i0) / (1.5 * SR), 0, 1)
    # ducking from a smoothed voice envelope
    block = int(0.02 * SR)
    venv = np.abs(voice[: n // block * block]).reshape(-1, block).max(axis=1)
    venv = np.convolve(venv, np.ones(25) / 25, mode="same")
    active = np.clip(venv / 0.05, 0, 1)
    duck = np.repeat(1 - 0.55 * active, block)
    gain[: len(duck)] *= duck
    dw = int(events["dead_word"] * SR)
    dip = np.ones(n, dtype=np.float32)
    dip[dw: dw + int(0.35 * SR)] = np.linspace(1, 0, int(0.35 * SR))
    dip[dw + int(0.35 * SR): dw + int(1.4 * SR)] = 0
    dip[dw + int(1.4 * SR): dw + int(2.6 * SR)] = np.linspace(0, 1, int(1.2 * SR))
    cut = int((events["now_word"] + 0.05) * SR)
    dip[cut:] = 0
    gain *= dip
    music *= gain[:, None]

    # per-frame voice level (30 fps) for the voicemail waveform
    fl = SR // 30
    lv = np.sqrt(np.mean(voice[: n // fl * fl].reshape(-1, fl) ** 2, axis=1))
    events["voice_env"] = [round(float(x), 3) for x in np.clip(lv / 0.12, 0, 1)]

    mix = music + (voice + fx)[:, None]
    mix = mix[: int(total * SR)]
    write_wav(OUT / "mix_raw.wav", mix)
    # Loud and clear: final loudness normalisation with a true-peak ceiling.
    run("ffmpeg", "-y", "-i", str(OUT / "mix_raw.wav"), "-af",
        "loudnorm=I=-14:TP=-1.0:LRA=9,aresample=48000", "-ar", str(SR), str(OUT / "mix.wav"))

    # ---- outputs ----
    timeline = {"total": round(total, 3), "scenes": scenes, "events": events,
                "typing": typing, "cues": cues, "s1_lines": S1_LINES, "title": TITLE,
                "s5_typed": S5_TYPED, "s5_final": S5_FINAL}
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1, ensure_ascii=False))

    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    srt = []
    for k, c in enumerate(cues, 1):
        label = "[Hindi] " if c["speaker"] == "KAMLA" and k == 1 else ""
        srt.append(f"{k}\n{ts(c['start'])} --> {ts(c['end'])}\n{label}{c['text']}\n")
    (OUT / "grace_loan_opening.srt").write_text("\n".join(srt), encoding="utf-8")

    lines = ["THE GRACE LOAN MEMORIAL CASE — voiceover lines", "Timings are from the rendered video.", ""]
    lines.append("SCENE 1 — THE VOICEMAIL")
    for (hi_txt, en_txt, roman), c in zip(KAMLA_LINES, [c for c in cues if c["speaker"] == "KAMLA"]):
        lines.append(f"[{ts(c['start'])[3:8]}] SMT. KAMLA SINGH (V.O., Hindi, crying): {roman}")
        lines.append(f"        Devanagari: {hi_txt}")
        lines.append(f"        Subtitle:   {en_txt}")
    for sc, title in ((3, "SCENE 3 — KABIR RAO"), (4, "SCENE 4 — THE HOSPITAL"), (5, "SCENE 5 — YOU ARE KABIR RAO")):
        lines += ["", title]
        for line, s in zip(NARRATION[sc], events[f"s{sc}_sentences"]):
            lines.append(f"[{ts(s['start'])[3:8]}] NARRATOR (V.O.): {line}")
    (OUT / "voiceover_lines.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"total {total:.2f}s")
    for s in scenes:
        print(f"  scene {s['id']}: {s['start']:6.2f} - {s['end']:6.2f}")


if __name__ == "__main__":
    main()
