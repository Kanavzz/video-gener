import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import DEFAULT_MODEL, generate, save_output


def _parse_inputs(pairs: List[str]) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}
    for pair in pairs:
        key, sep, raw = pair.partition("=")
        if not sep or not key:
            raise argparse.ArgumentTypeError(f"--input expects key=value, got {pair!r}")
        try:
            inputs[key] = json.loads(raw)  # numbers, booleans, lists
        except json.JSONDecodeError:
            inputs[key] = raw
    return inputs


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="video-gen",
        description="Generate a video from a text prompt using a model hosted on Replicate.",
    )
    parser.add_argument("prompt", help="text describing the video")
    parser.add_argument("-o", "--output", default="output.mp4", type=Path, help="where to save the video (default: output.mp4)")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Replicate model, e.g. owner/name or owner/name:version (default: {DEFAULT_MODEL})")
    parser.add_argument("-i", "--image", help="image path or URL for image-to-video")
    parser.add_argument("--image-param", default="first_frame_image", help="model input name for --image (default: first_frame_image)")
    parser.add_argument("--input", action="append", default=[], metavar="KEY=VALUE", help="extra model input; repeatable (e.g. --input duration=5)")
    args = parser.parse_args(argv)

    try:
        extra = _parse_inputs(args.input)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    print(f"Generating with {args.model} (this can take a few minutes)...", file=sys.stderr)
    try:
        output = generate(args.prompt, model=args.model, image=args.image, image_param=args.image_param, extra_input=extra)
        path = save_output(output, args.output)
    except Exception as e:  # surface API/auth errors without a traceback
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
