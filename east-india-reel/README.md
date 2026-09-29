# The East India Classroom Company (reel)

A 39.5 s vertical (1080×1920) comedy reel. The visuals are illustrated SVG scenes animated in
`scenes.html`. The voices are Kokoro neural TTS, with British voices for the professor and the judge.
Every sound effect (the orchestral sting, crowd groan, paper unrolling, record scratch, chanting,
gavel, trumpet and baroque outro music) is synthesized in `build_audio.py`. The cartoon mouths
follow the loudness of each voice track, so the lip-flap lines up with the audio.

```bash
npm install
pip install kokoro-onnx soundfile numpy scipy
mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ..
python3 build_audio.py build          # build/mix.wav + build/timeline.json
node render.js build out/east-india-classroom.mp4
./stills.sh 2,8,14                    # optional: contact sheet of frames at those times
```

Needs ffmpeg. Scene lengths live in `SCENES` in `build_audio.py`. Scenes 2 and 3 run about 1 s
longer than the script's 6 s, with that time taken back from scene 4, so the dialogue isn't rushed.
