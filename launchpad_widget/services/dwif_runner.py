"""D.W.I.F (Discord Widget Image Fixer) integration.

D.W.I.F is a Node.js tool (https://github.com/AjaxFNC-YT/D.W.I.F) that takes
any image and adds a transparent top strip + rounded top-right corner so it
fits Discord's widget image style perfectly.

This module shells out to the D.W.I.F Node.js script to process images
before they're uploaded to Discord. The result is a properly styled widget
image that displays correctly in the widget's circular/rounded clip path.

Layout:
    launchpad_widget/services/dwif_runner.py   <- this file
    dwif/                                      <- vendored D.W.I.F (added in
                                                 .github workflow or by user)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Where to look for the D.W.I.F install.  In a GitHub Actions runner we
# install it at runtime; locally it should be cloned once.
DWIF_DIR = Path(os.environ.get("DWIF_DIR", "dwif"))
DWIF_SCRIPT = DWIF_DIR / "scripts" / "process-image.mjs"


def is_available() -> bool:
    """Return True if Node + D.W.I.F are present and runnable."""
    if not shutil.which("node"):
        return False
    if not DWIF_SCRIPT.is_file():
        return False
    return True


def ensure_dwif_installed() -> bool:
    """Best-effort install of D.W.I.F and its Node deps.

    Returns True if D.W.I.F is ready to use after the call.
    """
    if is_available():
        return True
    if not shutil.which("node"):
        logger.warning("Node.js not found; D.W.I.F unavailable")
        return False
    if not shutil.which("npm"):
        logger.warning("npm not found; cannot install D.W.I.F")
        return False

    # Clone
    if not DWIF_DIR.is_dir():
        logger.info("Cloning D.W.I.F into %s", DWIF_DIR)
        try:
            subprocess.run(
                [
                    "git", "clone", "--depth=1",
                    "https://github.com/AjaxFNC-YT/D.W.I.F.git",
                    str(DWIF_DIR),
                ],
                check=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            logger.warning("Failed to clone D.W.I.F: %s", exc)
            return False

    # Install deps
    pkg = DWIF_DIR / "package.json"
    if not (DWIF_DIR / "node_modules").is_dir() and pkg.is_file():
        logger.info("Installing D.W.I.F dependencies (this may take a minute)...")
        try:
            subprocess.run(
                ["npm", "install", "--omit=dev", "--no-audit", "--no-fund"],
                cwd=str(DWIF_DIR),
                check=True,
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            logger.warning("Failed to install D.W.I.F deps: %s", exc)
            return False

    return is_available()


# Target output dimensions for the widget image.  Discord widgets render
# the image at 650x650 base resolution; we go to 2x (1300x1300) so the
# result is crisp on high-DPI displays.  The D.W.I.F rounded-corner /
# top-strip sizes are auto-calculated from these dimensions.
WIDGET_IMAGE_SIZE = 1300


def _prepare_square_image(
    input_path: Path,
    size: int = WIDGET_IMAGE_SIZE,
) -> Path | None:
    """Resize ``input_path`` to a square ``size x size`` PNG.

    Uses Pillow's cover-fit (center-crop to maintain aspect, then resize).
    The result is a square PNG saved next to the original with a ``-square``
    suffix.  Returns the new path, or None on failure.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow not installed; cannot pre-resize for D.W.I.F")
        return None
    try:
        with Image.open(input_path) as im:
            im = im.convert("RGBA")
            fitted = ImageOps.fit(im, (size, size), method=Image.LANCZOS, centering=(0.5, 0.5))
            out = input_path.with_name(f"{input_path.stem}-square.png")
            fitted.save(out, format="PNG", optimize=True)
            return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to pre-resize image: %s", exc)
        return None


def process_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    top_strip: int | None = None,
    radius: int | None = None,
    target_size: int = WIDGET_IMAGE_SIZE,
    timeout: float = 60.0,
) -> Path | None:
    """Run D.W.I.F on ``input_path`` and return the path to the processed image.

    The input image is first center-cropped to a square (``target_size`` x
    ``target_size``) and saved as a PNG, so D.W.I.F's auto-sizing works
    correctly and the final widget image fills the available canvas.  D.W.I.F
    then adds the transparent top strip + rounded top-right corner.

    Parameters
    ----------
    input_path:
        Local path to the image to process.
    output_path:
        Where to write the final result.  Defaults to ``<input>-dwif.png``
        next to the input file.
    top_strip, radius:
        Optional overrides for D.W.I.F's auto-computed values. ``None`` means
        "let D.W.I.F decide".
    target_size:
        Side length of the square output in pixels.  Defaults to
        ``WIDGET_IMAGE_SIZE`` (1300).
    """
    if not is_available():
        if not ensure_dwif_installed():
            logger.debug("D.W.I.F unavailable; skipping image styling")
            return None

    input_p = Path(input_path).resolve()
    if not input_p.is_file():
        return None

    # Step 1: convert the input to a square PNG of the target size.  This
    # is required because Discord widgets render the image at 1:1 aspect
    # and the original launch artwork is usually wide-aspect; if we don't
    # crop, the rocket ends up tiny in the middle of a wide empty frame.
    square_input = _prepare_square_image(input_p, size=target_size)
    if square_input is None or not square_input.is_file():
        logger.debug("Square pre-resize failed; falling back to raw input")
        square_input = input_p
        if square_input.suffix.lower() not in (".png", ".webp", ".gif"):
            # D.W.I.F needs a recognised extension on the input.
            renamed = square_input.with_suffix(".png")
            if not renamed.exists():
                try:
                    renamed.write_bytes(square_input.read_bytes())
                except OSError as exc:
                    logger.warning("Failed to make D.W.I.F-readable copy: %s", exc)
                    return None
            square_input = renamed

    # Step 2: D.W.I.F runs on the square input and writes a styled output.
    if output_path is None:
        out_basename = f"{input_p.stem}-dwif.png"
    else:
        out_basename = Path(output_path).name
    out_dwif_dir = DWIF_DIR / "output"
    out_dwif_dir.mkdir(parents=True, exist_ok=True)
    dwif_output = out_dwif_dir / out_basename
    final_output = input_p.with_name(out_basename)
    final_output.parent.mkdir(parents=True, exist_ok=True)

    # D.W.I.F's argv: process-image.mjs <inputPath> <outputName> <topStrip> <radius> <fastAnimated>
    cmd = ["node", str(DWIF_SCRIPT), str(square_input), dwif_output.name]
    if top_strip is not None:
        cmd.append(str(top_strip))
    else:
        cmd.append("")
    if radius is not None:
        cmd.append(str(radius))
    else:
        cmd.append("")
    cmd.append("true")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("D.W.I.F timed out after %.0fs", timeout)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("D.W.I.F failed to start: %s", exc)
        return None

    if result.returncode != 0:
        logger.warning(
            "D.W.I.F returned non-zero (%d): %s",
            result.returncode,
            (result.stderr or result.stdout or "").strip()[:300],
        )
        return None

    if not dwif_output.is_file():
        logger.warning("D.W.I.F did not write an output file")
        return None

    # Copy the result from D.W.I.F's output dir to the caller's expected location.
    try:
        final_output.write_bytes(dwif_output.read_bytes())
    except OSError as exc:
        logger.warning("Failed to copy D.W.I.F result: %s", exc)
        return None

    return final_output
