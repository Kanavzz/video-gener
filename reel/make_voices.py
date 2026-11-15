"""Synthesize every dialogue line with Kokoro (local neural TTS) into build/voice/.

Needs `pip install kokoro-onnx soundfile` and the model files in
../pitch-video/models/ (kokoro-v1.0.onnx, voices-v1.0.bin).
"""
import json
from pathlib import Path

import soundfile
from kokoro_onnx import Kokoro

from scenes import SCENES

HERE = Path(__file__).parent
MODELS = HERE.parent / "pitch-video" / "models"
OUT = HERE / "build" / "voice"
# speaker -> (voice, language, speed)
VOICES = {
    "OFFICIAL": ("bm_george", "en-gb", 1.0),
    "REPORTER": ("hm_omega", "en-us", 1.05),
    "STUDENT": ("hm_psi", "en-us", 0.98),
    "PROFESSOR": ("hm_omega", "en-us", 1.0),
    "CLASSMATE": ("hf_alpha", "en-us", 1.05),
}
# How each line is spoken (spelling help for the TTS); defaults to the subtitle text.
SPOKEN = {
    "We have abolished sati. Because we… are civilised.": "We have abolished, sati. Because we... are civilised.",
    "Wasn’t that Rammohun Roy’s scriptural argument?": "Wasn't that, Ram-mohun Roy's scriptural argument?",
    "…Next question.": "... Next question.",
    "So the civilising mission was… a sixty-year consent form?": "So the civilising mission was... a sixty-year consent form?",
    "And it didn’t start in 1857… or end in 1858.": "And it didn't start in eighteen fifty-seven... or end in eighteen fifty-eight.",
    "So the ‘High Noon’ had a really long afternoon.": "So the High Noon, had a really long afternoon.",
}

kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
OUT.mkdir(parents=True, exist_ok=True)
index = {}
for s in SCENES:
    for i, (who, text) in enumerate(s["lines"]):
        voice, lang, speed = VOICES[who]
        samples, rate = kokoro.create(SPOKEN.get(text, text), voice=voice, speed=speed, lang=lang)
        path = OUT / f"{s['id']}_{i}.wav"
        soundfile.write(str(path), samples, rate)
        index[path.name] = len(samples) / rate
        print(path.name, who, round(len(samples) / rate, 2))
(OUT / "durations.json").write_text(json.dumps(index, indent=2))
