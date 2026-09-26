"""Synthesize the voiceover sentence by sentence and write timeline.json.

Default engine is Kokoro (neural, natural-sounding), which needs `pip install
kokoro-onnx soundfile` and the model files in models/ (see README). Set
VOICE_ENGINE=festival to use festival's text2wave instead. Requires ffmpeg.
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "build"
ENGINE = os.environ.get("VOICE_ENGINE", "kokoro")
VOICE = os.environ.get("VOICE", "am_michael" if ENGINE == "kokoro" else "cmu_us_slt_arctic_hts")
MODELS = HERE / "models"
SPEED = float(os.environ.get("VOICE_SPEED", "1.15"))  # kokoro only
RATE = 48000
TARGET = 66.0  # seconds; script says ~65, keep under 70

# (section, id, caption, spoken text). Spoken text is spelled for the TTS voice.
SCRIPT = [
    (0, "hook1", "A factory owner pays his contractor for 52 workers today.",
     "A factory owner pays his contractor for fifty-two workers today."),
    (0, "hook2", "Only 41 walked in.", "Only forty-one walked in."),
    (0, "hook3", "He'll never know, because nobody is counting.",
     "He'll never know, because nobody is counting."),
    (1, "lakh", "India has 2.6 lakh registered factories,",
     "India has two point six lack registered factories,"),
    (1, "pct", "and 42% of their workers come through contractors.",
     "and forty-two percent of their workers come through contractors."),
    (1, "years", "That's the highest in 27 years of government data.",
     "That's the highest in twenty-seven years of government data."),
    (1, "register", "And at the truck gate? Still a handwritten register.",
     "And at the truck gate? Still a handwritten register."),
    (2, "meet", "Meet GateKeep AI, an AI analytics platform that plugs into the cameras a factory already owns.",
     "Meet Gate Keep A I. An A I analytics platform, that plugs into the cameras a factory already owns."),
    (2, "vision", "Our own vision API recognises workers' faces and reads every truck's number plate.",
     "Our own vision A P I recognises workers' faces, and reads every truck's number plate."),
    (2, "saves", "Then it does the part that saves money:",
     "Then it does the part that saves money."),
    (2, "checks", "It checks the headcount against the contractor's bill, and every truck against its e-way bill.",
     "It checks the headcount against the contractor's bill, and every truck against its e way bill."),
    (2, "whatsapp", "Mismatches go straight to the owner's WhatsApp, with the Excel sheet attached.",
     "Mismatches go straight to the owner's Whats App, with the Excel sheet attached."),
    (3, "team", "We're Kanav, Kyra, Ved, Krishang and Sahil.",
     "We're Kanav, Kyra, Ved, Krishang, and Sahil."),
    (3, "built", "In 24 hours we shaped the idea, built our deck, this video and our website, and started building our own API.",
     "In twenty-four hours, we shaped the idea, built our deck, this video, and our website, and started building our own A P I."),
    (3, "price", "Factories pay from ₹4,999 a month,",
     "Factories pay from four thousand, nine hundred and ninety-nine rupees a month,"),
    (3, "payback", "and catching just two ghost workers a day pays that back more than three times over.",
     "and catching just two ghost workers a day, pays that back more than three times over."),
    (4, "close", "GateKeep AI. Let's make your cameras count.",
     "Gate Keep A I. Let's make your cameras count."),
]

LEAD, GAP, SECTION_GAP, TAIL = 0.5, 0.22, 0.6, 1.6


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def duration(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def synthesizer():
    if ENGINE == "festival":
        def synth(text, wav):
            txt = wav.with_suffix(".txt")
            txt.write_text(text)
            run("text2wave", "-eval", f"(voice_{VOICE})", str(txt), "-o", str(wav))
        return synth

    import soundfile
    from kokoro_onnx import Kokoro
    kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))

    def synth(text, wav):
        samples, rate = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        soundfile.write(str(wav), samples, rate, subtype="PCM_16")
    return synth


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    synth = synthesizer()
    raw = []
    for _, sid, _, spoken in SCRIPT:
        wav = OUT / f"{sid}.raw.wav"
        synth(spoken, wav)
        raw.append(duration(wav))

    pauses = LEAD + TAIL + sum(
        SECTION_GAP if SCRIPT[i][0] != SCRIPT[i - 1][0] else GAP for i in range(1, len(SCRIPT)))
    tempo = min(1.3, max(1.0, sum(raw) / (TARGET - pauses)))

    cues, t, prev = [], LEAD, None
    for sec, sid, caption, _ in SCRIPT:
        src, dst = OUT / f"{sid}.raw.wav", OUT / f"{sid}.wav"
        run("ffmpeg", "-y", "-i", str(src), "-af", f"atempo={tempo:.4f},aresample={RATE}",
            "-ac", "1", "-sample_fmt", "s16", str(dst))
        if prev is not None:
            t += SECTION_GAP if sec != prev else GAP
        d = duration(dst)
        cues.append({"id": sid, "section": sec, "start": round(t, 3), "end": round(t + d, 3), "text": caption})
        t += d
        prev = sec
    total = t + TAIL

    # Assemble the voice track by placing each sentence at its start time.
    frames = bytearray(int(total * RATE) * 2)
    for cue in cues:
        with wave.open(str(OUT / f"{cue['id']}.wav")) as w:
            data = w.readframes(w.getnframes())
        off = int(cue["start"] * RATE) * 2
        frames[off:off + len(data)] = data
    with wave.open(str(OUT / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))

    sections = []
    for s in range(5):
        first = next(c for c in cues if c["section"] == s)
        sections.append(0.0 if s == 0 else round(first["start"] - 0.3, 3))
    timeline = {"total": round(total, 3), "tempo": round(tempo, 3), "sections": sections, "cues": cues}
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1))
    print(f"tempo {tempo:.3f}, total {total:.2f}s")
    for c in cues:
        print(f"  {c['start']:6.2f}-{c['end']:6.2f}  {c['id']}")


if __name__ == "__main__":
    main()
