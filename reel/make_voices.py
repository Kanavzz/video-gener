"""Synthesize every dialogue line into build/voice/<scene>_<n>.wav (24 kHz mono).

Default engine: Microsoft neural voices via edge-tts (`pip install edge-tts`),
which sound far more natural and have real British and Indian English voices.
VOICE_ENGINE=kokoro uses the local Kokoro model instead (models in
../pitch-video/models). Leading/trailing silence is trimmed so the scene
renderer controls every pause.
"""
import asyncio
import json
import os
import ssl
import subprocess
from pathlib import Path

from scenes import SCENES

HERE = Path(__file__).parent
OUT = HERE / "build" / "voice"
ENGINE = os.environ.get("VOICE_ENGINE", "edge")
RATE = os.environ.get("VOICE_RATE", "+8%")  # a touch faster than default, to fit 40 s
CA = "/root/.ccr/ca-bundle.crt"  # agent proxy CA; ignored when absent

# speaker -> (edge voice, pitch, extra rate)
EDGE = {
    "OFFICIAL": ("en-GB-RyanNeural", "-8Hz", "+0%"),       # pompous, 50ish
    "REPORTER": ("en-IN-PrabhatNeural", "-6Hz", "-2%"),     # older reporter, measured
    "STUDENT": ("en-IN-PrabhatNeural", "+6Hz", "-4%"),      # 18, deadpan
    "PROFESSOR": ("hi-IN-MadhurNeural", "+0Hz", "+2%"),     # Indian-accented English
    "CLASSMATE": ("en-IN-NeerjaExpressiveNeural", "+0Hz", "+0%"),
}
KOKORO = {"OFFICIAL": "bm_george", "REPORTER": "hm_omega", "STUDENT": "hm_psi", "PROFESSOR": "hm_omega", "CLASSMATE": "hf_alpha"}

# How each line is spoken (pronunciation / pacing help); defaults to the subtitle text.
SPOKEN = {
    "We have abolished sati. Because we… are civilised.": "We have abolished sati. Because we... are civilised.",
    "Wasn’t that Rammohun Roy’s scriptural argument?": "Wasn't that Rammohun Roy's scriptural argument?",
    "…Next question.": "Next question.",
    "So the civilising mission was… a sixty-year consent form?": "So the civilising mission was... a sixty-year consent form?",
    "And it didn’t start in 1857… or end in 1858.": "And it didn't start in eighteen fifty-seven... or end in eighteen fifty-eight.",
    "So the ‘High Noon’ had a really long afternoon.": "So the High Noon had a really long afternoon.",
    "Plot twist — that form changed history.": "Plot twist. That form changed history.",
}


def add_rates(a, b):
    return f"{int(a.rstrip('%')) + int(b.rstrip('%')):+d}%"


def trim(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,"
                    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse",
                    "-ac", "1", "-ar", "24000", str(dst)], check=True)


async def edge_all(jobs):
    import edge_tts
    import edge_tts.communicate as comm
    if Path(CA).exists():
        comm._SSL_CTX = ssl.create_default_context(cafile=CA)
    for who, text, path in jobs:
        voice, pitch, extra = EDGE[who]
        mp3 = path.with_suffix(".mp3")
        await edge_tts.Communicate(text, voice, rate=add_rates(RATE, extra), pitch=pitch).save(str(mp3))
        trim(mp3, path)
        mp3.unlink()


def kokoro_all(jobs):
    import soundfile
    from kokoro_onnx import Kokoro
    models = HERE.parent / "pitch-video" / "models"
    k = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))
    for who, text, path in jobs:
        samples, rate = k.create(text, voice=KOKORO[who], speed=1.08, lang="en-gb" if who == "OFFICIAL" else "en-us")
        raw = path.with_suffix(".raw.wav"); soundfile.write(str(raw), samples, rate)
        trim(raw, path); raw.unlink()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(who, SPOKEN.get(text, text), OUT / f"{s['id']}_{i}.wav")
            for s in SCENES for i, (who, text) in enumerate(s["lines"])]
    asyncio.run(edge_all(jobs)) if ENGINE == "edge" else kokoro_all(jobs)
    durs = {}
    for _, _, p in jobs:
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))
        durs[p.name] = round(d, 2); print(p.name, durs[p.name])
    (OUT / "durations.json").write_text(json.dumps(durs, indent=2))
