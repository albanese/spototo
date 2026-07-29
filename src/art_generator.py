"""
Generate a 16x16 pixel-art icon for a song via Replicate's Retro Diffusion
model, choosing the best of several candidates with a vision-model judge.

Pipeline (all on Replicate):
  1. extract_subject(): a small LLM distills a song title into ONE concrete
     drawable subject ("Candy Cane Crush!" -> "candy cane"), because the image
     model draws a clear object beautifully but turns a compound title to noise.
  2. generate_pixel_art(): generates NUM_CANDIDATES icons at native 16x16 in
     the "mc_item" style (Minecraft-style items — high, consistent quality with
     built-in transparency, so no local background removal is needed), then a
     vision model picks the candidate that most clearly reads as the subject.

Single generations are a coin flip in quality; best-of-N + judge turns that
into reliably-good icons. Every external step degrades gracefully: if the LLM
or the judge fails, we fall back to the raw title / the first candidate so an
icon is always produced.
"""
import base64
import io
import logging
import os
import re
import time

import replicate
import requests
from PIL import Image, ImageDraw
from replicate.exceptions import ReplicateError

log = logging.getLogger("yoto-pixel-pipeline.art")

MODEL = "retro-diffusion/rd-fast"
ICON_SIZE = 16
STYLE = "mc_item"  # crisp, consistent single-object icons with transparency
NUM_CANDIDATES = int(os.environ.get("ICON_CANDIDATES", "8"))

SUBJECT_MODEL = "meta/meta-llama-3-8b-instruct"
SUBJECT_SYSTEM = (
    "You turn a kids song title into ONE simple concrete object to draw as a "
    "16x16 pixel-art icon. Reply with only 2-5 words naming the object and its "
    "main colors, no punctuation, no explanation."
)

# Community models (unlike official ones) must be pinned to a version, or
# replicate.run hits the model-level endpoint and 404s. Override via env if the
# pinned version is ever removed.
JUDGE_MODEL = os.environ.get(
    "ICON_JUDGE_MODEL",
    "lucataco/qwen2-vl-7b-instruct:bf57361c75677fc33d480d0c5f02926e621b2caa2000347cb74aeae9d2ca07ee",
)

# Replicate throttles accounts with <$5 credit to ~6 requests/min (burst 1),
# and each song fires several calls back-to-back, so retry 429s with backoff.
_RATE_LIMIT_RETRIES = 6
_RATE_LIMIT_WAIT = 15


def _run(model, inp):
    """replicate.run with backoff on 429 rate-limit responses."""
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            return replicate.run(model, input=inp)
        except ReplicateError as exc:
            throttled = getattr(exc, "status", None) == 429 or "429" in str(exc)
            if throttled and attempt < _RATE_LIMIT_RETRIES - 1:
                time.sleep(_RATE_LIMIT_WAIT)
                continue
            raise


def extract_subject(title: str, api_token: str = None) -> str:
    """Distill a song title to a short drawable subject. Falls back to the
    raw title if the LLM step fails, so icon generation never blocks on it."""
    if api_token:
        os.environ["REPLICATE_API_TOKEN"] = api_token
    try:
        output = _run(
            SUBJECT_MODEL,
            {
                "prompt": f'Song title: "{title}"\nObject:',
                "system_prompt": SUBJECT_SYSTEM,
                "max_tokens": 12,
                "temperature": 0.2,
            },
        )
        text = output if isinstance(output, str) else "".join(output)
        subject = text.strip().strip('".').splitlines()[0].strip()
        return subject or title
    except Exception:
        return title


def generate_pixel_art(prompt: str, api_token: str = None, subject: str = None) -> bytes:
    """Returns PNG bytes of the best of NUM_CANDIDATES 16x16 pixel-art icons.

    `subject` is the short human phrase the judge scores against (e.g. "candy
    cane"); if omitted we fall back to the full prompt.
    """
    if api_token:
        os.environ["REPLICATE_API_TOKEN"] = api_token

    output = _run(
        MODEL,
        {
            "prompt": prompt,
            "width": ICON_SIZE,
            "height": ICON_SIZE,
            "style": STYLE,
            "num_images": NUM_CANDIDATES,
        },
    )
    items = output if isinstance(output, list) else [output]
    candidates = [_to_image(_item_to_bytes(it)) for it in items]

    best = _judge(candidates, subject or prompt)
    out = io.BytesIO()
    candidates[best].save(out, format="PNG")
    return out.getvalue()


def _judge(candidates, subject: str) -> int:
    """Return the index of the candidate that best depicts `subject`, via a
    vision model shown a single numbered grid. Falls back to 0 on any failure."""
    if len(candidates) == 1:
        return 0
    try:
        grid_png = _numbered_grid(candidates)
        data_uri = "data:image/png;base64," + base64.b64encode(grid_png).decode()
        n = len(candidates)
        prompt = (
            f"This image shows {n} candidate pixel-art icons numbered #1 to #{n}, "
            f"each meant to depict: {subject}. Pick the ONE that most clearly and "
            f"attractively reads as {subject} at tiny size, with a clean shape and "
            f"good colors. Reply with ONLY the number."
        )
        output = _run(JUDGE_MODEL, {"media": data_uri, "prompt": prompt, "max_new_tokens": 16})
        text = output if isinstance(output, str) else "".join(output)
        m = re.search(r"\d+", text)
        if m:
            idx = int(m.group()) - 1
            if 0 <= idx < n:
                log.info(f"Judge picked candidate #{idx + 1} of {n} for {subject!r}")
                return idx
        log.warning(f"Judge reply unparseable ({text!r}); using candidate #1")
    except Exception:
        log.exception("Judge failed; using candidate #1")
    return 0


def _numbered_grid(candidates, cell: int = 140, cols: int = 4) -> bytes:
    """Tile candidates into a numbered grid (upscaled) for the vision judge."""
    rows = (len(candidates) + cols - 1) // cols
    pad, lbl = 10, 22
    W = cols * (cell + pad) + pad
    H = rows * (cell + pad + lbl) + pad
    grid = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(grid)
    for i, im in enumerate(candidates):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad + lbl)
        grid.alpha_composite(im.resize((cell, cell), Image.NEAREST), (x, y))
        draw.text((x + 4, y + cell + 4), f"#{i + 1}", fill=(0, 0, 0, 255))
    out = io.BytesIO()
    grid.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def _item_to_bytes(item) -> bytes:
    if hasattr(item, "read"):
        return item.read()
    if isinstance(item, (bytes, bytearray)):
        return bytes(item)
    if isinstance(item, str):
        resp = requests.get(item, timeout=60)
        resp.raise_for_status()
        return resp.content
    raise TypeError(f"Unrecognized Replicate output type: {type(item)!r}")


def _to_image(raw_png_bytes: bytes, size: int = ICON_SIZE) -> Image.Image:
    """Open the model output as an exactly `size`x`size` RGBA image."""
    img = Image.open(io.BytesIO(raw_png_bytes)).convert("RGBA")
    if img.size != (size, size):
        # Defensive: some styles ignore the small size request and return
        # larger output. NEAREST keeps hard pixel edges when that happens.
        img = img.resize((size, size), Image.NEAREST)
    return img
