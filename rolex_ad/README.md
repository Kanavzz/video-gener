# "Time Is Earned" — Rolex spec ad (40s)

A spec advertisement cut from Pexels stock footage. It is **not affiliated with or
endorsed by Rolex SA**, and it uses the name only as plain text (no crown logo).

## Setup

```bash
cd rolex_ad
pip install -r requirements.txt          # ffmpeg must also be on PATH
cp .env.example .env                     # then put your key in .env
```

`.env` holds `PEXELS_API_KEY=...` and is gitignored. Get a key at https://www.pexels.com/api/.

The network needs to reach `api.pexels.com` (search, API route only), `www.pexels.com` and
`videos.pexels.com` (clip downloads), and `speech.platform.bing.com` (edge-tts).

## Run

```bash
python download_clips.py     # 1. one clip per shot -> clips/, clips/manifest.json, credits.txt
python make_voiceover.py     # 2. four VO lines -> work/vo/, warns if a line overruns its shot
python render.py --draft     # 3. quick render -> final/rolex_spec_ad.mp4
python render.py             #    final-quality render
```

Each step only redoes its own work, so after you swap a clip you just re-run `render.py`.

## No Pexels API key? (current situation)

Pexels has paused new API keys, so this cut was assembled with `fetch_by_id.py`. It downloads a
specific clip through Pexels' own free-download link, which needs no key. Find a clip on
pexels.com, copy its page URL, then run:

```bash
python fetch_by_id.py 5 https://www.pexels.com/video/close-up-view-of-a-rolex-watch-6230465/ \
    --photographer "Mitchel Durfee" --start 3.5
python render.py --draft
```

`--start` sets how many seconds into the source clip the shot begins. The script picks the
1080p rendition when one exists and updates `clips/manifest.json` and `credits.txt`. The exact
commands used for this cut are in `clips.sh`.

## Swapping clips

- **Let Pexels pick a different one:** `python download_clips.py --shot 5`. This skips the
  current clip and takes the next best match. You can repeat `--shot`.
- **Change the search:** edit that shot's `queries` in `config.py`. The first term is
  tried first, and the others are fallbacks. Then run `download_clips.py --shot N`.
- **Use a specific clip:** drop the mp4 in `clips/` and edit that shot's `file`
  (plus `pexels_url` and `photographer` for credits) in `clips/manifest.json`.

Clips are trimmed from 1s in (when there's room), scaled to cover 1920x1080, conformed to 24fps
and graded before editing.

## Tweaking

Everything lives in `config.py`:

- **Timing:** shot durations, 0.6s crossfade, and the 0.5s VO offset.
- **Ken Burns:** `"auto"` measures motion and zooms only static-looking clips. Set
  `True` or `False` per shot to force it.
- **Voiceover:** lines, voice and rate.
- **Music:** gain, fades, and the shot it enters on.
- **Titles:** text and fonts.

The colour grade (desaturation, crushed blacks, warm highlights, vignette) is the `GRADE`
ffmpeg filter chain at the top of `render.py`.

## Music

Drop a `music.mp3` in this folder and re-run `render.py`. It enters with shot 2, so shot 1
opens on silence. It plays at -18 dB with a 2s fade-in and a 3s fade-out, and it ducks
automatically under the voiceover. Without the file, the ad renders with voiceover only.

## Layout

| Path | What |
|---|---|
| `config.py` | shot list, VO script, timings, look |
| `download_clips.py` | Pexels search + download, writes `credits.txt` |
| `make_voiceover.py` | edge-tts narration |
| `render.py` | edit, grade, titles, letterbox, audio mix |
| `fonts/` | Cormorant Garamond (SIL OFL) from Google Fonts |
| `credits.txt` | Pexels source URL and photographer for every clip |
| `final/rolex_spec_ad.mp4` | the output (not committed, since `*.mp4` is gitignored) |
