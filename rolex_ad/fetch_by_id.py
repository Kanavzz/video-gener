"""Step 1 without an API key: download a specific Pexels video by its ID for one shot.

Pexels paused new API keys, so this uses the site's own free-download link instead
(https://www.pexels.com/download/video/<id>/), which needs no key. Find the ID at the
end of the clip's page URL, e.g. pexels.com/video/close-up-of-watch-mechanism-11965370/.

Usage:
  python fetch_by_id.py SHOT PAGE_URL --photographer "Name" [--start SECONDS]
                   [--zoom 1.15] [--anchor-x 0.85] [--query "term used"]
"""

import argparse
import json
import re
import subprocess

import requests

import config
from download_clips import download, write_credits


def resolve(video_id):
    """Pick the 1080p rendition if Pexels has one, else whatever the download link serves."""
    r = requests.get(f"https://www.pexels.com/download/video/{video_id}/", allow_redirects=False, timeout=30)
    top = r.headers.get("Location")
    if not top:
        raise SystemExit(f"Pexels returned {r.status_code} for video {video_id}")
    fps = re.search(r"_(\d+fps)\.mp4", top)
    base = f"https://videos.pexels.com/video-files/{video_id}/{video_id}"
    for size in ("1920_1080", "2048_1080"):
        if fps:
            url = f"{base}-hd_{size}_{fps.group(1)}.mp4"
            if requests.head(url, timeout=30).status_code == 200:
                return url
    return top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shot", type=int)
    ap.add_argument("page_url")
    ap.add_argument("--photographer", default="(not confirmed — see Pexels page)")
    ap.add_argument("--start", type=float, help="seconds into the clip to start the shot")
    ap.add_argument("--zoom", type=float, help="punch in, e.g. 1.15")
    ap.add_argument("--anchor-x", type=float, help="horizontal crop anchor, 0 = left, 1 = right")
    ap.add_argument("--query", help="search term that found it (defaults to the brief's term)")
    args = ap.parse_args()

    shot = next(s for s in config.SHOTS if s["id"] == args.shot)
    video_id = int(re.search(r"(\d+)/?$", args.page_url).group(1))
    url = resolve(video_id)
    config.CLIPS_DIR.mkdir(exist_ok=True)
    fname = f"shot{args.shot}_{video_id}.mp4"
    download(url, config.CLIPS_DIR / fname)

    w, h = map(int, re.search(r"_(\d+)_(\d+)_\d+fps", url).groups())
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(config.CLIPS_DIR / fname)], capture_output=True, text=True).stdout)
    query = args.query or shot["queries"][0]
    manifest = json.loads(config.MANIFEST.read_text()) if config.MANIFEST.exists() else {}
    manifest[str(args.shot)] = {
        "shot": args.shot, "file": fname, "query": query,
        "substituted": query != shot["queries"][0], "requested_query": shot["queries"][0],
        "pexels_id": video_id, "pexels_url": args.page_url,
        "title": args.page_url.rstrip("/").split("/")[-1].rsplit("-", 1)[0].replace("-", " "),
        "photographer": args.photographer, "width": w, "height": h, "duration": round(dur, 2),
        **{k: v for k, v in (("start", args.start), ("zoom", args.zoom), ("anchor_x", args.anchor_x))
           if v is not None},
    }
    config.MANIFEST.write_text(json.dumps(manifest, indent=2))
    write_credits(manifest)
    print(f"shot {args.shot}: {fname} {w}x{h} {dur:.1f}s")


if __name__ == "__main__":
    main()
