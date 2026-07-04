"""Discord widget image styling (port of D.W.I.F to pure Pillow).

The Discord profile widget image is rendered inside a rounded-rectangle
clip path. To make an image fit cleanly we need to:

1. Resize it to a square (the widget image is rendered at 1:1)
2. Add a transparent top strip so the title can overlay cleanly
3. Round the top-right corner to match the widget's clip

The original D.W.I.F (https://github.com/AjaxFNC-YT/D.W.I.F) does this
in Node.js with sharp. This module reimplements the same algorithm
in pure Pillow so we don't need Node.js at runtime.

Reference (the math): D.W.I.F's auto-calibration is anchored at 512x512
and grows with the image's diagonal via a power law.  We use the same
formulas so the output matches what D.W.I.F would produce at 512px.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Where to look for the optional D.W.I.F install (kept for compat with the
# old shell-out code path).  The Python port below is the default; D.W.I.F
# is only used if the user explicitly sets ``DWIF_USE_NODE=1``.
DWIF_DIR = Path(os.environ.get("DWIF_DIR", "dwif"))
DWIF_SCRIPT = DWIF_DIR / "scripts" / "process-image.mjs"
USE_NODE_DWIF = os.environ.get("DWIF_USE_NODE", "").lower() in ("1", "true", "yes")


# --- D.W.I.F calibration constants (from the upstream project) --------------- #
_REF_SIZE = 512  # everything is calibrated against a 512x512 reference
_STRIP_BASE = 17  # pixels of top strip at the reference size
_RADIUS_BASE = 36  # pixels of corner radius at the reference size
_STRIP_EXP = math.log(54 / 17) / math.log(math.sqrt(1844 * 853) / _REF_SIZE)
_RADIUS_EXP = math.log(172 / 36) / math.log(math.sqrt(1844 * 853) / _REF_SIZE)


# --- Public target dimensions ----------------------------------------------- #
# 512x512 is what the reference implementation uses and what D.W.I.F was
# calibrated for. Discord scales the image to fit the widget; the
# calibration math handles the resize cleanly.
WIDGET_IMAGE_SIZE = 512


def _auto(base: float, exponent: float, size: int) -> int:
    """D.W.I.F's auto-calculation: grow proportionally to the image diagonal."""
    return max(0, round(base * (size / _REF_SIZE) ** exponent))


def _fix_widget_image(img: Any, top_strip: int, radius: int) -> Any:
    """Add a transparent top strip and round the top-right corner.

    This is a Pillow port of D.W.I.F's single-frame transform.

    Parameters
    ----------
    img:
        A Pillow ``Image`` in ``RGBA`` mode, already resized to the
        target square size.
    top_strip:
        Pixels of transparent band to add at the top.
    radius:
        Corner radius in pixels.

    Returns
    -------
    A new ``Image`` with the top strip + rounded corner applied.
    """
    from PIL import Image, ImageChops, ImageDraw

    w, h = img.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(img, (0, top_strip))  # shifting down leaves a transparent strip on top

    # Clip the top-right corner to a circle.  We build a mask: white
    # everywhere except for a square in the top-right, then restore the
    # quarter-circle that the widget's clip path keeps.
    radius = min(radius, w, max(h - top_strip, 0))
    if radius > 0:
        mask = Image.new("L", (w, h), 255)
        md = ImageDraw.Draw(mask)
        # Clear the corner box (everything to the right of x=w-radius and
        # above y=top_strip+radius is in the corner).
        md.rectangle([w - radius, top_strip, w, top_strip + radius], fill=0)
        # Restore the quarter-circle that the widget actually shows.
        cx, cy = w - radius, top_strip + radius
        md.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
        # Apply the mask to the alpha channel.
        r, g, b, a = canvas.split()
        canvas = Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, mask)))
    return canvas


def _prepare_square_pillow(input_path: Path, size: int = WIDGET_IMAGE_SIZE) -> Path | None:
    """Center-crop the input to a square ``size x size`` PNG.

    Uses Pillow's ``Image.fit`` which center-crops to maintain aspect
    ratio and then resizes to the target dimensions.

    Returns the new file path, or None on failure.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow not installed; cannot pre-resize image")
        return None
    try:
        with Image.open(input_path) as im:
            im = im.convert("RGBA")
            # ``ImageOps.fit`` does center-crop + resize in one call.
            # Available across all Pillow versions.
            fitted = ImageOps.fit(im, (size, size), method=Image.LANCZOS, centering=(0.5, 0.5))
            out = input_path.with_name(f"{input_path.stem}-square.png")
            fitted.save(out, format="PNG", optimize=True)
            return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to pre-resize image: %s", exc)
        return None


# --- Optional Node.js D.W.I.F (kept for compat; not the default) ----------- #


def is_node_dwif_available() -> bool:
    """True if the user opted into the Node D.W.I.F subprocess path."""
    if not USE_NODE_DWIF:
        return False
    if not shutil.which("node"):
        return False
    if not DWIF_SCRIPT.is_file():
        return False
    return True


def ensure_node_dwif_installed() -> bool:
    if not USE_NODE_DWIF:
        return False
    if not shutil.which("node"):
        return False
    if not shutil.which("npm"):
        return False
    if not DWIF_DIR.is_dir():
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", "https://github.com/AjaxFNC-YT/D.W.I.F.git", str(DWIF_DIR)],
                check=True, timeout=120,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to clone D.W.I.F: %s", exc)
            return False
    if not (DWIF_DIR / "node_modules").is_dir() and (DWIF_DIR / "package.json").is_file():
        try:
            subprocess.run(
                ["npm", "install", "--omit=dev", "--no-audit", "--no-fund"],
                cwd=str(DWIF_DIR), check=True, timeout=300,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to install D.W.I.F deps: %s", exc)
            return False
    return is_node_dwif_available()


# --- Public API ------------------------------------------------------------ #


def process_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    top_strip: int | None = None,
    radius: int | None = None,
    target_size: int = WIDGET_IMAGE_SIZE,
) -> Path | None:
    """Style ``input_path`` for the Discord widget and return the new path.

    The image is:

    1. Center-cropped to a square of ``target_size x target_size`` (Pillow).
    2. Given a transparent top strip and a rounded top-right corner
       using D.W.I.F's calibration math.

    Output is saved as a PNG next to the input file.  The returned
    path is what the rest of the daemon should upload to Discord.
    """
    input_p = Path(input_path).resolve()
    if not input_p.is_file():
        return None

    # Step 1: square the image.
    square_input = _prepare_square_pillow(input_p, size=target_size)
    if square_input is None or not square_input.is_file():
        logger.warning("Square pre-resize failed")
        return None

    # Step 2: D.W.I.F calibration for the top strip and corner radius.
    if top_strip is None:
        top_strip = _auto(_STRIP_BASE, _STRIP_EXP, target_size)
    if radius is None:
        radius = _auto(_RADIUS_BASE, _RADIUS_EXP, target_size)

    # Step 3: apply the fix.
    try:
        from PIL import Image
        with Image.open(square_input) as im:
            im = im.convert("RGBA")
            fixed = _fix_widget_image(im, top_strip, radius)
            if output_path is None:
                out = square_input.with_name(f"{square_input.stem}-dwif.png")
            else:
                out = Path(output_path).resolve()
                out.parent.mkdir(parents=True, exist_ok=True)
            fixed.save(out, format="PNG", optimize=True)
            return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Widget-fix failed: %s", exc)
        return None
