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


def process_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    top_strip: int | None = None,
    radius: int | None = None,
    timeout: float = 60.0,
) -> Path | None:
    """Run D.W.I.F on ``input_path`` and return the path to the processed image.

    Parameters
    ----------
    input_path:
        Local path to the image to process.
    output_path:
        Where to write the result. Defaults to ``<input>-dwif.png`` next to
        the input file.
    top_strip, radius:
        Optional overrides for D.W.I.F's auto-computed values. ``None`` means
        "let D.W.I.F decide".

    Returns
    -------
    The output path on success, or ``None`` if D.W.I.F failed.
    """
    if not is_available():
        if not ensure_dwif_installed():
            logger.debug("D.W.I.F unavailable; skipping image styling")
            return None

    input_p = Path(input_path).resolve()
    if not input_p.is_file():
        return None
    # D.W.I.F only accepts .png, .webp, .gif outputs.  If our cached file
    # is ``.bin`` we still pass it to D.W.I.F (it sniffs the actual format
    # from the bytes for the input) but force the output extension to .png.
    if output_path is None:
        out_basename = f"{input_p.stem}-dwif.png"
        out_dwif_dir = DWIF_DIR / "output"
        out_dwif_dir.mkdir(parents=True, exist_ok=True)
        dwif_output = out_dwif_dir / out_basename
        final_output = input_p.with_name(out_basename)
    else:
        final_output = Path(output_path).resolve()
        # Ensure final output has a supported extension
        if final_output.suffix.lower() not in (".png", ".webp", ".gif"):
            final_output = final_output.with_suffix(".png")
        dwif_output = DWIF_DIR / "output" / final_output.name
    final_output.parent.mkdir(parents=True, exist_ok=True)

    # D.W.I.F accepts absolute input paths directly.  We rename the file
    # to .png (if needed) so D.W.I.F's format sniffer picks the right
    # encoder.  We work on a temp copy next to the original.
    if input_p.suffix.lower() not in (".png", ".webp", ".gif"):
        renamed = input_p.with_suffix(".png")
        if not renamed.exists():
            try:
                renamed.write_bytes(input_p.read_bytes())
            except OSError as exc:
                logger.warning("Failed to make D.W.I.F-readable copy: %s", exc)
                return None
        dwif_input = renamed
    else:
        dwif_input = input_p

    # D.W.I.F's argv: process-image.mjs <inputPath> <outputName> <topStrip> <radius> <fastAnimated>
    # ``outputName`` is a filename (relative to OUTPUT_DIR), not a full path.
    cmd = ["node", str(DWIF_SCRIPT), str(dwif_input), dwif_output.name]
    if top_strip is not None:
        cmd.append(str(top_strip))
    else:
        cmd.append("")
    if radius is not None:
        cmd.append(str(radius))
    else:
        cmd.append("")
    # fastAnimated default
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
