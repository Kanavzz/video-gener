"""Step 2: voice each line, polish it so it sounds less synthetic, and time the subtitles.

Kokoro (the default) runs in its own Python 3.12 env (.venv-tts); edge-tts is the fallback.
"""

import asyncio
import json
import os
import re
import subprocess

import config

# Light "in the room" polish: trim rumble, a touch of chest warmth, soften the synthetic
# top end, gentle compression and a short, quiet room reflection.
POLISH = ",".join([
    "highpass=f=70",
    "equalizer=f=160:t=q:w=1:g=2.5",
    "equalizer=f=6500:t=q:w=1.5:g=-2.5",
    "acompressor=threshold=-20dB:ratio=2.5:attack=15:release=180:makeup=2",
    "aecho=0.9:0.6:28|47:0.10|0.06",
])


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def voice_kokoro(vo_dir):
    subprocess.run([str(config.TTS_PYTHON), str(config.ROOT / "tts_kokoro.py"), config.KOKORO_VOICE,
                    str(config.KOKORO_SPEED), str(vo_dir), *(l["say"] for l in config.VOICEOVER)],
                   check=True)
    return [vo_dir / f"line{i}.wav" for i in range(1, len(config.VOICEOVER) + 1)], \
        json.loads((vo_dir / "words.json").read_text())


def voice_edge(vo_dir):
    import edge_tts

    async def run():
        # aiohttp ignores HTTPS_PROXY unless told, so pass it through explicitly.
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        paths = []
        for i, line in enumerate(config.VOICEOVER, 1):
            path = vo_dir / f"line{i}.mp3"
            await edge_tts.Communicate(line["say"], config.EDGE_VOICE, rate=config.EDGE_RATE,
                                       proxy=proxy).save(str(path))
            paths.append(path)
        return paths
    return asyncio.run(run()), [[] for _ in config.VOICEOVER]   # no word timings -> one cue per line


def cues(text, words, start, dur):
    """Split a line into sentence-sized subtitle cues, timed from the word timestamps."""
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p]
    if len(parts) == 1 or len(words) < len(parts):
        first = words[0]["start"] if words else 0.0
        return [{"text": text, "start": start + first, "end": start + dur}]
    out, w = [], 0
    for part in parts:
        n = len(re.findall(r"[\w']+", part))
        chunk = [x for x in words[w:] if re.search(r"\w", x["word"])][:n]
        w = words.index(chunk[-1]) + 1
        out.append({"text": part, "start": start + chunk[0]["start"], "end": start + chunk[-1]["end"]})
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"]                      # hold each cue until the next one starts
    out[-1]["end"] = start + dur
    return out


def main():
    vo_dir = config.WORK_DIR / "vo"
    vo_dir.mkdir(parents=True, exist_ok=True)
    raw, words = voice_kokoro(vo_dir) if config.TTS_ENGINE == "kokoro" else voice_edge(vo_dir)
    starts = config.shot_starts()
    lengths = {s["id"]: s["duration"] for s in config.SHOTS}
    lines = []
    for i, (line, src, toks) in enumerate(zip(config.VOICEOVER, raw, words), 1):
        path = vo_dir / f"line{i}_polished.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", POLISH, "-ar", "48000",
                        str(path)], check=True)
        dur = duration(src)
        start = starts[line["shot"]] + line["offset"]
        room = lengths[line["shot"]] - line["offset"]
        flag = "" if dur <= room else f"   (runs {dur - room:.2f}s into the next shot)"
        print(f"line {i} @ {start:5.2f}s  {dur:.2f}s  \"{line['text']}\"{flag}")
        lines.append({**line, "file": str(path), "start": start, "duration": dur,
                      "cues": cues(line["text"], toks, start, dur)})
    if lines[-1]["start"] + lines[-1]["duration"] > config.total_duration():
        print("!! the last line runs past the end of the ad")
    (vo_dir / "voiceover.json").write_text(json.dumps(lines, indent=2))


if __name__ == "__main__":
    main()
