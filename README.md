# video-gen

A small command-line tool that generates videos with models hosted on [Replicate](https://replicate.com). The model runs on Replicate's servers, so you don't need a GPU.

## Install

```bash
pip install git+https://github.com/kanavzz/video-gener.git
# or, from a clone:
pip install -e .
```

Get an API token at https://replicate.com/account/api-tokens and export it:

```bash
export REPLICATE_API_TOKEN=r8_...
```

## Usage

```bash
# Text to video (default model: minimax/video-01)
video-gen "a corgi surfing a wave at sunset, cinematic" -o corgi.mp4

# Image to video (a local file is uploaded; a URL is passed through)
video-gen "the camera slowly pushes in" -i photo.jpg -o push.mp4

# Pick any Replicate video model and pass it extra inputs
video-gen "neon city in the rain" -m google/veo-3 -o city.mp4
video-gen "a paper boat" -m owner/model --input duration=5 --input aspect_ratio=16:9
```

Input names vary by model, so check the model's page on Replicate for the right `--input` keys and the image input name (set it with `--image-param`; the default is `first_frame_image`).

Set `VIDEO_GEN_MODEL` to change the default model.

## Python

```python
from pathlib import Path
from video_gen import generate, save_output

save_output(generate("a cat playing piano"), Path("cat.mp4"))
```

## Development

```bash
pip install -e '.[dev]'
pytest
```
