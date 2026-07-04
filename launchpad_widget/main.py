"""Package entry point."""

from __future__ import annotations

import logging
import sys

from .config import AppConfig
from .services.orchestrator import build_default_orchestrator
from .utils.logging_setup import configure_logging

logger = logging.getLogger("launchpad_widget.main")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    config_path = argv[0] if argv else None

    config = AppConfig.load(config_path)
    configure_logging(config.log_file, level=config.log_level)
    logger.info(
        "Discord LaunchPad Widget starting up (preferred source=%s)",
        config.preferred_source,
    )

    problems = config.validate()
    if problems:
        for p in problems:
            logger.error("Config error: %s", p)
        logger.error("Set the missing values in your environment or config.json and re-run.")
        return 2

    orchestrator = build_default_orchestrator(config)
    try:
        orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fatal error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
