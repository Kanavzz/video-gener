# "Time Is Earned": Rolex spec ad (15s)

A spec advertisement cut from Pexels stock footage. It is **not affiliated with or
endorsed by Rolex SA**, and it uses the name only as plain text (no crown logo).

**The cut:**

| Shot | Footage | Sound |
|---|---|---|
| 1 | Watch movement macro | Ticking |
| 2 | Climber on snow | Mountain wind |
| 3 | Diver in a sea cave | Underwater rumble and bubbles |
| 4 | Surfer on a big wave | Rough sea |
| 5 | Wave at sunset | Breaking waves |
| 6 | Hero watch, with "ROLEX" | Low hum, soft tick |
| — | End card | The tick carries over |

It has a natural-sounding voiceover (Kokoro), subtitles in the lower letterbox bar,
crossfades, a colour grade and 2.39:1 bars.

## Setup

```bash
cd rolex_ad
pip install -r requirements.txt          # ffmpeg must also be on PATH

# Kokoro (the voice) needs Python 3.12 and runs in its own env:
uv venv -p python3.12 .venv-tts
VIRTUAL_ENV=.venv-tts uv pip install --index-strategy unsafe-best-match \
    --extra-index-url https://download.pytorch.org/whl/cpu torch "kokoro>=0.9.4" soundfile "numpy<2"
# Kokoro's English model needs spaCy's en_core_web_sm. If github.com is blocked, the wheel is on Hugging Face:
curl -L -o /tmp/en_core_web_sm-3.7.1-py3-none-any.whl \
    https://huggingface.co/spacy/en_core_web_sm/resolve/main/en_core_web_sm-any-py3-none-any.whl
VIRTUAL_ENV=.venv-tts uv pip install /tmp/en_core_web_sm-3.7.1-py3-none-any.whl
```

The network needs to reach these hosts:

- `www.pexels.com` and `videos.pexels.com`: clips.
- `huggingface.co`: Kokoro model, first run only.
- `assets.mixkit.co`: sound effects, first render only.
- `speech.platform.bing.com`: only if you switch to edge-tts.

## Run

```bash
./clips.sh                   # 1. fetch the six Pexels clips -> clips/, manifest.json, credits.txt
python make_voiceover.py     # 2. voice the lines, polish them, time the subtitles -> work/vo/
python render.py --draft     # 3. quick render (about 3.5 min) -> final/rolex_spec_ad.mp4
python render.py             #    final quality
```

Each step only redoes its own work. After swapping a clip, re-run `render.py`. After changing
the script or voice, re-run `make_voiceover.py` and then `render.py`.

## Changing things (all in `config.py`)

- **Voice:** set `KOKORO_VOICE`. `bm_george` is the default British male. You can also try
  `bm_fable`, `bm_daniel`, `am_michael`, or `af_heart`, a very natural female voice.
  `KOKORO_SPEED` sets the pace. Set `TTS_ENGINE = "edge"` to go back to edge-tts.
- **Lines and subtitles:** `VOICEOVER`. `say` is what the voice reads; `...` adds a pause.
  `text` is the subtitle. Sentences become separate subtitle cues, timed to the words.
- **Background sounds:** each shot's `sfx` is a list of `(Mixkit id, gain dB, ffmpeg filter)`.
  Find more at https://mixkit.co/free-sound-effects/. The number in a sound's preview URL is
  its id. The files download into `sfx/` on first render; they aren't committed, because
  Mixkit's licence allows use but not redistribution.
- **Timing:** shot durations, the `CROSSFADE` length, and the end card's length.

The colour grade is the `GRADE` ffmpeg chain in `render.py`. The voice polish (warmth, softer
top end, light compression, a touch of room) is `POLISH` in `make_voiceover.py`.

## Swapping clips

Pexels has paused new API keys, so clips are fetched by ID through Pexels' free-download link:

```bash
python fetch_by_id.py 4 https://www.pexels.com/video/surfer-riding-the-big-waves-of-a-sea-2873484/ \
    --photographer "Evgenia Kirpichnikova" --start 2.5     # optional: --zoom 1.15 --anchor-x 0.8
python render.py --draft
```

`--start` sets how many seconds into the source clip the shot begins. Record your choice in
`clips.sh` so the cut stays reproducible. If you do have a Pexels API key, put it in `.env` as
`PEXELS_API_KEY` and `python download_clips.py --shot N` will search for you.

## Layout

| Path | What |
|---|---|
| `config.py` | shots, sounds, voiceover script, timings, look |
| `clips.sh`, `fetch_by_id.py` | the Pexels clips in this cut |
| `download_clips.py` | Pexels API search (needs a key) and `credits.txt` writer |
| `make_voiceover.py`, `tts_kokoro.py` | voice, polish and subtitle timing |
| `render.py` | edit, grade, titles, subtitles, letterbox, sound mix |
| `fonts/` | Cormorant Garamond (SIL OFL) from Google Fonts |
| `credits.txt` | every footage, sound and voice source |
| `final/rolex_spec_ad.mp4` | the output (not committed, since `*.mp4` is gitignored) |
