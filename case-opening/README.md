# The Grace Loan Memorial Case — opening video

```bash
pip install edge-tts numpy      # neural TTS, no API key needed
npm install                     # fonts; Playwright + Chromium must be available
python3 build_audio.py build    # voices, SFX, music, mix.wav, timeline.json, .srt, voiceover_lines.txt
node render.js build out/grace_loan_opening.mp4
node render.js build build/stills --stills 5,30,60   # preview frames
```

- `build_audio.py` holds the script, voices (NARRATOR `en-IN-PrabhatNeural`, KAMLA `hi-IN-SwaraNeural`),
  code-generated SFX/music and the mix. Scene timing follows the voice lines. `NO_TTS=1` skips TTS.
- `scenes.html` has one `sceneN()` function per scene, driven by `build/timeline.json`.
- End card: "Presented by Chakravyuh" (`#endcard` in `scenes.html`).
