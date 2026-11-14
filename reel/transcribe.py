"""Time each scene's subtitles to the speech in its generated clip.

Runs Whisper on Replicate over each clip's audio, then lays the script's lines
over the detected speech, snapping line boundaries to Whisper segment edges.
Writes build/cues/<id>.json (and <id>_whisper.json for reference).
"""
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from generate_clips import API, call
from scenes import SCENES

B = Path(__file__).parent / "build"


def whisper(mp3):
    version = call("GET", f"{API}/models/openai/whisper")["latest_version"]["id"]
    uri = "data:audio/mpeg;base64," + base64.b64encode(mp3.read_bytes()).decode()
    pred = call("POST", f"{API}/predictions", {"version": version, "input": {"audio": uri, "language": "en"}})
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(3)
        pred = call("GET", pred["urls"]["get"])
    if pred["status"] != "succeeded":
        raise RuntimeError(pred.get("error"))
    return [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in pred["output"]["segments"]]


def lay_out(lines, segs, duration=8.0):
    segs = [s for s in segs if s["text"]] or [{"start": 0.4, "end": duration - 0.4, "text": ""}]
    t0, t1 = segs[0]["start"], min(segs[-1]["end"], duration - 0.1)
    edges = sorted({s["start"] for s in segs[1:]} | {s["end"] for s in segs[:-1]})
    weights = [len(t) for _, t in lines]
    cues, start, acc = [], t0, 0
    for i, (who, text) in enumerate(lines):
        acc += weights[i]
        end = t1 if i == len(lines) - 1 else t0 + (t1 - t0) * acc / sum(weights)
        if i < len(lines) - 1 and edges:
            end = min(edges, key=lambda e: abs(e - end)) if min(abs(e - end) for e in edges) < 0.8 else end
        pad_in = 0.1 if i == 0 else 0.0
        pad_out = 0.25 if i == len(lines) - 1 else 0.0
        cues.append({"who": who, "text": text, "start": round(max(0, start - pad_in), 2), "end": round(end + pad_out, 2)})
        start = end
    return cues


if __name__ == "__main__":
    (B / "cues").mkdir(parents=True, exist_ok=True)
    for s in SCENES:
        clip = B / "clips" / f"{s['id']}.mp4"
        if not clip.exists():
            continue
        mp3 = B / "cues" / f"{s['id']}.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-vn", "-ac", "1", "-b:a", "64k", str(mp3)], check=True)
        segs = whisper(mp3)
        (B / "cues" / f"{s['id']}_whisper.json").write_text(json.dumps(segs, indent=2))
        cues = lay_out(s["lines"], segs)
        (B / "cues" / f"{s['id']}.json").write_text(json.dumps(cues, indent=2, ensure_ascii=False))
        print(s["id"], json.dumps(segs), "->", [(c["start"], c["end"]) for c in cues], flush=True)
