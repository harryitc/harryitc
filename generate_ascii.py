#!/usr/bin/env python3
"""Turn a portrait photo into the ASCII art block used by the profile SVG.

Run this by hand whenever you swap the photo, then commit ascii_art.txt:

    python generate_ascii.py --crop 280,600,1520,1924
    python generate_ascii.py --invert          # light subject on dark background

The output is deliberately editable. Opening ascii_art.txt and deleting stray
background characters is normal and usually the difference between "noisy" and
"looks good".
"""

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).parent

# Sparse to dense. Index by brightness, so index 0 is what a dark pixel becomes.
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

# Terminal characters are roughly twice as tall as they are wide, so rows have
# to be sampled at half the rate of columns or the face comes out stretched.
CHAR_ASPECT = 0.5


def parse_crop(raw):
    if not raw:
        return None
    parts = [int(p) for p in raw.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop needs 4 numbers: left,top,right,bottom")
    return tuple(parts)


def to_ascii(image, width, ramp, contrast, floor):
    image = image.convert("L")
    if contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(contrast)

    height = max(1, round(image.height / image.width * width * CHAR_ASPECT))
    image = image.resize((width, height), Image.LANCZOS)

    pixels = image.load()
    scale = (len(ramp) - 1) / 255
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            value = pixels[x, y]
            # Anything dimmer than the floor is treated as background and dropped,
            # which is what keeps a busy photo from filling the frame with noise.
            row.append(" " if value < floor else ramp[round(value * scale)])
        rows.append("".join(row))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="avatar.jpg", help="source photo")
    parser.add_argument("--output", default="ascii_art.txt", help="where to write the art")
    parser.add_argument("--width", type=int, default=46, help="width in characters")
    parser.add_argument("--crop", type=parse_crop, default=None,
                        help="left,top,right,bottom in source pixels")
    parser.add_argument("--invert", action="store_true",
                        help="swap light and dark; use when the subject is darker than the background")
    parser.add_argument("--contrast", type=float, default=1.6,
                        help="1.0 leaves the photo alone; higher separates subject from background")
    parser.add_argument("--floor", type=int, default=0,
                        help="brightness 0-255 below which a pixel becomes blank background")
    args = parser.parse_args()

    source = ROOT / args.input
    if not source.exists():
        raise SystemExit(f"no such image: {source}")

    image = Image.open(source)
    if args.crop:
        image = image.crop(args.crop)
    if args.invert:
        image = ImageOps.invert(image.convert("RGB"))

    rows = to_ascii(image, args.width, RAMP, args.contrast, args.floor)
    # Trailing spaces would widen the SVG for no reason.
    text = "\n".join(row.rstrip() for row in rows)

    destination = ROOT / args.output
    destination.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {destination} ({args.width}x{len(rows)} characters)")
    print(text)


if __name__ == "__main__":
    main()
