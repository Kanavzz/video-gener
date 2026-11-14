"""Generate each scene's 8-second clip on Replicate (default: google/veo-3-fast).

Usage: python3 generate_clips.py [scene_id ...] [--force]
Needs REPLICATE_API_TOKEN (any value works when a proxy injects the real key).
Clips land in build/clips/<scene_id>.mp4; existing clips are skipped unless --force.
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scenes import SCENES, full_prompt

HERE = Path(__file__).parent
OUT = HERE / "build" / "clips"
MODEL = os.environ.get("REEL_MODEL", "google/veo-3-fast")
API = "https://api.replicate.com/v1"
TOKEN = os.environ.get("REPLICATE_API_TOKEN", "proxy-injected")


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def generate(scene, force=False):
    path = OUT / f"{scene['id']}.mp4"
    if path.exists() and not force:
        return f"{scene['id']}: exists, skipped"
    inputs = {"prompt": full_prompt(scene), "aspect_ratio": "9:16", "duration": 8,
              "generate_audio": True, "resolution": "1080p"}
    inputs.update(json.loads(os.environ.get("REEL_EXTRA_INPUT", "{}")))
    pred = call("POST", f"{API}/models/{MODEL}/predictions", {"input": inputs})
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(8)
        pred = call("GET", pred["urls"]["get"])
    if pred["status"] != "succeeded":
        return f"{scene['id']}: {pred['status']}: {pred.get('error')}"
    url = pred["output"][0] if isinstance(pred["output"], list) else pred["output"]
    path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, path)
    (path.with_suffix(".json")).write_text(json.dumps({"id": pred["id"], "model": MODEL, "input": inputs}, indent=2))
    return f"{scene['id']}: saved {path} ({pred.get('metrics', {}).get('predict_time', '?')}s)"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    todo = [s for s in SCENES if not args or s["id"] in args]
    with ThreadPoolExecutor(len(todo)) as pool:
        for msg in pool.map(lambda s: generate(s, "--force" in sys.argv), todo):
            print(msg, flush=True)
