"""Step 1: search Pexels for each shot, download one clip per shot, write credits.txt.

Usage:  python download_clips.py            # skips shots already in the manifest
        python download_clips.py --shot 5   # re-pick a single shot
        python download_clips.py --force    # re-pick everything
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

import config

API = "https://api.pexels.com/videos/search"


def load_env():
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        sys.exit("PEXELS_API_KEY is not set. Put it in rolex_ad/.env (see .env.example).")
    return key


def pick_file(video):
    """Best rendition: exactly 1920x1080 if offered, else the smallest landscape one >= 1280 wide."""
    files = [f for f in video["video_files"] if f.get("width") and f.get("height")
             and f["width"] > f["height"] and f.get("file_type") == "video/mp4"]
    exact = [f for f in files if (f["width"], f["height"]) == (1920, 1080)]
    if exact:
        return exact[0]
    big = sorted((f for f in files if f["width"] >= 1280), key=lambda f: f["width"])
    big_enough = [f for f in big if f["width"] >= 1920]
    return (big_enough or big[::-1] or [None])[0]


def search(key, query, min_seconds, used_ids):
    resp = requests.get(API, headers={"Authorization": key}, timeout=30, params={
        "query": query, "orientation": "landscape", "size": "medium", "per_page": 40})
    resp.raise_for_status()
    candidates = []
    for video in resp.json().get("videos", []):
        if video["id"] in used_ids or video["duration"] < min_seconds:
            continue
        f = pick_file(video)
        if f is None:
            continue
        # Prefer true 1080p, then clips that aren't far longer than we need (tighter shots).
        rank = (0 if (f["width"], f["height"]) == (1920, 1080) else 1, abs(video["duration"] - 12))
        candidates.append((rank, video, f))
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1:] if candidates else None


def download(url, dest):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
        tmp.rename(dest)


def write_credits(manifest):
    lines = ["Stock footage — all clips from Pexels (https://www.pexels.com), used under the Pexels License.", ""]
    for entry in sorted(manifest.values(), key=lambda e: e["shot"]):
        lines.append(f"Shot {entry['shot']}: {entry['title']}")
        lines.append(f"  Video by {entry['photographer']} — {entry['pexels_url']}")
        lines.append(f"  Search term: \"{entry['query']}\"")
    lines += ["", "Voiceover: Microsoft Edge neural TTS (en-GB-RyanNeural) via edge-tts.",
              "Font: Cormorant Garamond (SIL Open Font License), Google Fonts."]
    if config.MUSIC.exists():
        lines.append("Music: music.mp3 (supplied by the producer).")
    config.CREDITS.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", type=int, action="append", help="only (re)download this shot")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    key = load_env()
    config.CLIPS_DIR.mkdir(exist_ok=True)
    manifest = json.loads(config.MANIFEST.read_text()) if config.MANIFEST.exists() else {}

    for shot in config.SHOTS:
        sid = str(shot["id"])
        redo = args.force or (args.shot and shot["id"] in args.shot)
        if sid in manifest and not redo and Path(config.CLIPS_DIR / manifest[sid]["file"]).exists():
            continue
        if args.shot and shot["id"] not in args.shot:
            continue
        used = {e["pexels_id"] for k, e in manifest.items() if k != sid}
        if redo and sid in manifest:
            used.add(manifest[sid]["pexels_id"])  # ask for something different
        need = max(5, shot["duration"] + config.CROSSFADE + 1)
        found = None
        for query in shot["queries"]:
            found = search(key, query, need, used)
            if found:
                break
            print(f"  shot {sid}: nothing usable for \"{query}\"")
        if not found:
            print(f"!! shot {sid}: no usable clip for any search term")
            continue
        video, f = found
        fname = f"shot{sid}_{video['id']}.mp4"
        print(f"shot {sid}: \"{query}\" -> {video['url']} ({f['width']}x{f['height']}, {video['duration']}s)")
        download(f["link"], config.CLIPS_DIR / fname)
        manifest[sid] = {
            "shot": shot["id"], "file": fname, "query": query,
            "substituted": query != shot["queries"][0], "requested_query": shot["queries"][0],
            "pexels_id": video["id"], "pexels_url": video["url"],
            "title": video["url"].rstrip("/").split("/")[-1].rsplit("-", 1)[0].replace("-", " ") or f"video {video['id']}",
            "photographer": video["user"]["name"], "photographer_url": video["user"]["url"],
            "width": f["width"], "height": f["height"], "duration": video["duration"],
        }
        config.MANIFEST.write_text(json.dumps(manifest, indent=2))

    write_credits(manifest)
    print(f"\n{len(manifest)}/{len(config.SHOTS)} shots ready. Credits -> {config.CREDITS}")
    for e in sorted(manifest.values(), key=lambda e: e["shot"]):
        sub = f"  (substituted for \"{e['requested_query']}\")" if e["substituted"] else ""
        print(f"  {e['shot']}. {e['title']} — {e['photographer']} — {e['width']}x{e['height']}, {e['duration']}s{sub}")


if __name__ == "__main__":
    main()
