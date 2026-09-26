import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_MODEL = os.environ.get("VIDEO_GEN_MODEL", "minimax/video-01")


def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    image: Optional[str] = None,
    image_param: str = "first_frame_image",
    extra_input: Optional[Dict[str, Any]] = None,
) -> Any:
    """Run a video model on Replicate and return its raw output."""
    import replicate

    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise RuntimeError(
            "REPLICATE_API_TOKEN is not set. Get a token at "
            "https://replicate.com/account/api-tokens and export it."
        )

    model_input: Dict[str, Any] = {"prompt": prompt}
    if image:
        # Local files are uploaded by the client; URLs are passed through.
        model_input[image_param] = image if image.startswith(("http://", "https://")) else open(image, "rb")
    model_input.update(extra_input or {})

    try:
        return replicate.run(model, input=model_input)
    finally:
        for value in model_input.values():
            if hasattr(value, "close"):
                value.close()


def save_output(output: Any, path: Path) -> Path:
    """Write a model's video output to ``path``.

    Handles the shapes Replicate models return: a FileOutput, a URL string,
    or a list of either (the first item is used).
    """
    if isinstance(output, (list, tuple)):
        if not output:
            raise RuntimeError("Model returned no output.")
        output = output[0]

    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(output, "read"):
        path.write_bytes(output.read())
    elif isinstance(output, str):
        with urllib.request.urlopen(output) as resp:
            path.write_bytes(resp.read())
    else:
        raise RuntimeError(f"Unexpected model output: {output!r}")
    return path
