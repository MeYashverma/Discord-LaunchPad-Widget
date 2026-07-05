# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Mermaid diagrams throughout documentation (architecture, API flow, module layout, lifecycle)
- Comprehensive `docs/` folder (ARCHITECTURE, SETUP, HOSTING, FIELDS, RATE_LIMITS, IMAGE_PIPELINE)
- Pure-Pillow port of D.W.I.F (no Node.js dependency)
- Detailed credits and references to upstream projects
- LICENSE file (MIT)
- Issue templates (bug report, feature request)
- CHANGELOG.md
- CONTRIBUTING.md

### Changed
- `dwif_runner.py` — ported from D.W.I.F subprocess to pure Pillow, using the same calibration math as the reference implementation
- `orchestrator.py` — wires the D.W.I.F step into the cycle, dedupes patches
- `payload_builder.py` — fixed to use the correct `data.dynamic` body shape
- `http_client.py` — Discord-bot-style User-Agent header
- `discord_updater.py` — retry once on transient 401s
- README — full rewrite with mermaid architecture diagram and credits

### Fixed
- Body shape of widget PATCH (`{"identities": [...]}` → `{"username": ..., "data": {"dynamic": [...]}}`)
- Image field type (text → image with nested url)
- Field count (15 → 14, matching the widget editor)
- `image_priority` mapping (`rocket` → `rocket_image_url`, etc.)
- `launch_artwork_url` extraction from LL2 dict response
- `DISCORD_TARGET_CHANNEL_ID` previously in Variables (must be in Secrets)
- Self-dispatch loop (was `if: always()`, now `if: success()`)
- Image clipping: rocket was being cut off at the top, now properly bottom-aligned
- D.W.I.F corner radius and top strip were too small, now calibrated for proper widget fit

## [0.1.0] — 2026-07-04

### Added
- Initial release
- Launch Library 2 + SpaceX API providers
- Discord widget PATCH via dynamic identities
- Image upload to Discord channel for CDN URLs
- GitHub Actions self-dispatching daemon
- Basic D.W.I.F integration (Node.js subprocess)

### Known issues
- Widget body shape was wrong (silently accepted with 204 but not stored)
- Image field type was wrong (text instead of image with nested url)
- Extra `seconds_to_launch` field not in editor
- D.W.I.F corner radius and top strip were too small for proper widget fit
