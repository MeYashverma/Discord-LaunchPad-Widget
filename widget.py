#!/usr/bin/env python3
"""Top-level entry point for the Discord LaunchPad Widget.

This file exists so the documented ``python widget.py`` invocation works
without users having to know about the inner package layout. The actual
logic lives in :mod:`launchpad_widget.main`.
"""

from launchpad_widget.main import main


if __name__ == "__main__":
    raise SystemExit(main())
