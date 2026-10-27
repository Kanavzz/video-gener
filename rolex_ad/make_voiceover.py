"""Step 2: synthesise each voiceover line with edge-tts and check it fits its shot."""

import asyncio
import json
import subprocess

import edge_tts

import config


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


async def main():
    vo_dir = config.WORK_DIR / "vo"
    vo_dir.mkdir(parents=True, exist_ok=True)
    starts = config.shot_starts()
    lengths = {s["id"]: s["duration"] for s in config.SHOTS}
    lines = []
    for i, line in enumerate(config.VOICEOVER, 1):
        path = vo_dir / f"line{i}_shot{line['shot']}.mp3"
        await edge_tts.Communicate(line["text"], config.VOICE, rate=config.VOICE_RATE).save(str(path))
        dur = duration(path)
        start = starts[line["shot"]] + config.VO_OFFSET
        room = lengths[line["shot"]] - config.VO_OFFSET
        flag = "" if dur <= room else f"   <-- runs {dur - room:.2f}s past the end of shot {line['shot']}"
        print(f"line {i} @ {start:5.2f}s  {dur:.2f}s  \"{line['text']}\"{flag}")
        lines.append({**line, "file": str(path), "start": start, "duration": dur})
    (vo_dir / "voiceover.json").write_text(json.dumps(lines, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
