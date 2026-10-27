"""Kokoro TTS worker, run with the Python 3.12 env in .venv-tts (Kokoro doesn't support 3.13 yet).

Usage: .venv-tts/bin/python tts_kokoro.py VOICE SPEED OUT_DIR "line one" "line two" ...
Writes lineN.wav (24 kHz) and words.json with per-word start/end times for each line.
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline


def main():
    voice, speed, out_dir, *lines = sys.argv[1:]
    out = Path(out_dir)
    pipeline = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")   # "b" = British, "a" = US
    words = []
    for i, text in enumerate(lines, 1):
        audio, tokens, offset = [], [], 0.0
        for result in pipeline(text, voice=voice, speed=float(speed)):
            chunk = result.audio.numpy()
            for t in result.tokens or []:
                if t.start_ts is not None:
                    tokens.append({"word": t.text, "start": offset + t.start_ts, "end": offset + t.end_ts})
            audio.append(chunk)
            offset += len(chunk) / 24000
        sf.write(out / f"line{i}.wav", np.concatenate(audio), 24000)
        words.append(tokens)
    (out / "words.json").write_text(json.dumps(words, indent=2))


if __name__ == "__main__":
    main()
