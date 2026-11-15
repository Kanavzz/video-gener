# Reel: "Colonial PR Team, 1829–1858"

Builds Kanav Agarwal's 40-second vertical (9:16) reel from the production script:
five 8-second AI clips (Google Veo 3 Fast on Replicate, which also speaks the
dialogue), with the fact-check context boxes, subtitles, BREAKING lower-third,
timeline, framed notice and end card burned on top.

## Image route (used for the delivered reel; no Replicate key needed)

Scene images were generated with Canva's AI image generator from the script's
prompts and exported at 1080x1920 into `build/images/scene1..5.png`.

```bash
python3 fix_images.py      # repaint smartboard (scene 4) + notice (scene 5), upscale 2x
python3 make_voices.py     # Kokoro neural voices for every line (models in ../pitch-video/models)
python3 render_scenes.py   # camera moves (camera.json) + voices + news sting -> build/clips, cues
python3 build_timing.py
node compose.js            # -> out/Kanav_Agarwal_Reel.mp4
```

## Video-model route (Replicate)

```bash
export REPLICATE_API_TOKEN=r8_...      # any placeholder works if a proxy injects the key
python3 generate_clips.py              # -> build/clips/scene1..5.mp4 (skips existing; --force to redo)
python3 transcribe.py                  # Whisper on Replicate -> subtitle timings in build/cues/
python3 build_timing.py                # -> build/scenes.json
node compose.js                        # -> out/Kanav_Agarwal_Reel.mp4
```

Regenerate a single scene with `python3 generate_clips.py scene3 --force`, then
rerun the last three steps. Preview the overlays without clips:
`python3 build_timing.py && node compose.js --stills` (writes build/stills/).

- `scenes.py`: character sheet, per-scene prompts, dialogue lines and on-screen text.
- `overlays.html`: the overlay graphics, drawn per frame by `window.render(t)`.
- Needs ffmpeg, Python 3 and Node with Playwright/Chromium.
