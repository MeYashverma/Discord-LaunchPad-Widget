# 🚀 Discord LaunchPad Widget

> **Live space-launch tracker → Discord profile widget.**
> Fetches the next scheduled rocket launch from free public APIs, transforms
> it into Discord's Dynamic Identity JSON, and updates your profile widget
> automatically — no PC, no VPS, no frontend.

```
No VPS             No Paid APIs        No Local Machine
No Manual Updates  No Frontend         100% Cloud Automated
```

---

## ✨ What this is

A cloud daemon (designed to run as a long-lived GitHub Actions job) that
keeps your Discord profile widget in sync with the **next scheduled space
launch**. Every few minutes it:

1. Fetches upcoming launches from **Launch Library 2** and the **SpaceX API**.
2. Normalises the data onto a single `Launch` shape.
3. Picks the best available image (rocket > mission patch > artwork > pad).
4. Builds a Discord Dynamic Identity JSON payload (text + numeric fields).
5. `PATCH`es the widget through Discord's official endpoint.
6. Loops, with a graceful exit before the runner's hard timeout.

This is **not** a website, **not** a dashboard, and **not** a frontend
application. The only output is the JSON payload sent to Discord and the
image asset used to populate the widget.

---

## 📊 What the widget displays

For the next valid launch the widget exposes 14 fields (matching the
exact layout of the widget editor):

| # | Field name      | Type    | Example                                |
| - | --------------- | ------- | -------------------------------------- |
| 1 | `mission`       | text    | `Falcon 9 Block 5 | Starlink Group 10-50` |
| 2 | `rocket`        | text    | `Falcon 9 Block 5`                     |
| 3 | `provider`      | text    | `SpaceX`                               |
| 4 | `status`        | text    | `Go for Launch` / `Hold: Weather`      |
| 5 | `countdown`     | text    | `T-04d 12:35:21`                       |
| 6 | `window`        | text    | `2026-07-08 14:30 UTC → 18:30 UTC`     |
| 7 | `site`          | text    | `Space Launch Complex 40`              |
| 8 | `location`      | text    | `Cape Canaveral SFS, FL, USA`          |
| 9 | `country`       | text    | `United States of America`             |
| 10| `orbit`         | text    | `Low Earth Orbit`                      |
| 11| `crew`          | text    | `Uncrewed` (or `J. Smith, A. Patel +2`)|
| 12| `type`          | text    | `Communications` / `Human Spaceflight` |
| 13| `probability`   | number  | `85`                                   |
| 14| `image`         | image   | (Discord CDN URL)                      |

The set of field names must match the **Data Field** names you create in
the Discord widget editor — see [`SETUP.md`](docs/SETUP.md).

---

## 🛰 Data sources

All data sources are free and require no authentication for the volumes
this widget needs.

| Source                                                | Used for                              |
| ----------------------------------------------------- | ------------------------------------- |
| [Launch Library 2](https://thespacedevs.com/llapi)    | Primary — covers every operator       |
| [SpaceX API](https://github.com/r-spacex/SpaceX-API)  | Secondary — covers SpaceX in detail   |
| [NASA APIs](https://api.nasa.gov/)                    | Optional enrichment (APOD, NEO, etc.) |
| [Where The ISS At](https://wheretheiss.at/)           | Optional ISS position bonus           |
| [Open Notify](http://open-notify.org/)                | Available for future extensions       |

Free tier limits (Launch Library 2: 15 req/hr) are absorbed by the built-in
TTL cache and the GitHub-Actions-cron update cadence.

---

## 🏗 Architecture

```
            ┌────────────────────────┐
            │  GitHub Actions cron   │  (or self-dispatch loop)
            └───────────┬────────────┘
                        ▼
            ┌────────────────────────┐
            │      widget.py         │   (entry point)
            └───────────┬────────────┘
                        ▼
            ┌────────────────────────┐
            │  WidgetOrchestrator    │   loop, runtime budget,
            │                        │   graceful shutdown
            └──┬───────────┬─────────┘
               │           │
   ┌───────────▼─┐   ┌─────▼───────┐   ┌──────────────────┐
   │ Providers   │   │ ImageService│   │ PayloadBuilder   │
   │  - LL2      │   │  - download │   │  - text fields   │
   │  - SpaceX   │   │  - cache    │   │  - numeric fields│
   │  - bonus    │   │  - fallback │   │  - image field   │
   └─────────────┘   └─────────────┘   └────────┬─────────┘
                                                ▼
                                      ┌──────────────────┐
                                      │ DiscordUpdater   │
                                      │  - PATCH         │
                                      │  - rate-limited  │
                                      │  - state file    │
                                      └────────┬─────────┘
                                               ▼
                                    PATCH /applications/{APP}/users/{USER}
                                          /identities/0/profile
```

Module layout:

```
launchpad_widget/
├── apis/
│   ├── base.py             # LaunchProvider protocol
│   ├── launch_library.py   # TheSpaceDevs LL2 client
│   ├── spacex.py           # r-spacex v4 client
│   └── bonus.py            # NASA / ISS enrichment
├── services/
│   ├── image_service.py    # download, cache, prioritise
│   ├── payload_builder.py  # Launch → Discord JSON
│   ├── discord_updater.py  # PATCH + state de-dup
│   └── orchestrator.py     # main loop, runtime budget
├── utils/
│   ├── cache.py            # TTL + image caches
│   ├── http_client.py      # requests + retry + 429
│   ├── retry.py            # generic backoff helper
│   └── logging_setup.py    # rotating file + console
├── assets/
│   └── fallback.png        # bundled fallback image
├── config.py
├── models.py
└── main.py
```

---

## ⚙️ Setup

See [`docs/SETUP.md`](docs/SETUP.md) for the full one-time guide. The
high-level steps are:

1. **Create a Discord application** at the [Developer Portal](https://discord.com/developers/applications).
2. **Create the profile widget** under *Activities → Profile Widget* and add
   Data Fields matching the names listed above.
3. **Invite a bot** to your account (or use a user account) and grab the
   `DISCORD_BOT_TOKEN`, `DISCORD_APPLICATION_ID`, and `DISCORD_USER_ID`.
4. **Add GitHub Secrets** to this repository with those three values.
5. **Run the workflow** manually once from the Actions tab, then leave it
   alone — the daemon self-dispatches subsequent runs.

---

## ▶️ Running locally

```bash
pip install -r requirements.txt
cp config.example.json config.json   # then edit it
export DISCORD_APPLICATION_ID=...
export DISCORD_USER_ID=...
export DISCORD_BOT_TOKEN=...
python widget.py
```

To inspect the payload that would be sent without hitting Discord:

```bash
DRY_RUN=true python widget.py
# or, for a single snapshot:
python scripts/inspect_payload.py
```

---

## ⚙️ Configuration

All knobs are environment variables (or keys in `config.json`). See
`config.example.json` for the canonical list. The most useful ones:

| Variable                      | Default                  | Purpose                                  |
| ----------------------------- | ------------------------ | ---------------------------------------- |
| `PREFERRED_SOURCE`            | `launch_library`         | `launch_library` or `spacex`             |
| `UPDATE_INTERVAL_SECONDS`     | `300`                    | Time between cycles                      |
| `MIN_PATCH_INTERVAL_SECONDS`  | `60`                     | Throttle for Discord PATCHes             |
| `MAX_RUNTIME_SECONDS`         | `21000`                  | Soft runtime budget (loop exits cleanly) |
| `CACHE_TTL_SECONDS`           | `120`                    | API response cache                       |
| `IMAGE_CACHE_TTL_SECONDS`     | `86400`                  | Downloaded image cache                   |
| `IMAGE_PRIORITY`              | `rocket,mission_patch,…` | Order in which images are tried          |
| `DRY_RUN`                     | `false`                  | Log the payload, don't PATCH Discord    |
| `LOG_LEVEL`                   | `INFO`                   | `DEBUG` / `INFO` / `WARNING` / `ERROR`   |
| `NASA_API_KEY`                | `DEMO_KEY`               | Optional enrichment                      |

---

## 🖼 Image hosting

Discord's profile widget image fields must point to an `https://` URL on
Discord's CDN. The widget ships a small helper to do this for you:

```bash
DISCORD_BOT_TOKEN=... DISCORD_TARGET_CHANNEL_ID=... \
  python scripts/upload_image.py cache/images/img_xxxxxxxx.png
```

The script prints the resulting Discord CDN URL on stdout. The daemon's
state file (`last_payload.json`) records the last successfully PATCHed
payload so identical updates are skipped.

> 💡 The bundled `launchpad_widget/assets/fallback.png` is always used when
> no other image is available, so the widget never goes blank.

---

## 🛟 Error handling

* **Network errors** — exponential backoff up to `HTTP_RETRIES` times.
* **429 rate limits** — honour the upstream `Retry-After` header.
* **Provider failures** — fall through to the next configured provider.
* **Image failures** — silently fall through to the next image in priority
  order, ending with the bundled fallback.
* **No upcoming launch** — log a warning, sleep, try again next cycle.
* **Identical payload** — skip the PATCH (saves rate-limit budget).
* **Crash mid-cycle** — outer `try` in the loop catches and logs, never
  kills the daemon.
* **Runtime budget** — soft cap, exits cleanly so the workflow can
  self-dispatch a fresh run.

---

## 📚 Documentation

* [`docs/SETUP.md`](docs/SETUP.md) — one-time Discord app + widget setup
* [`docs/HOSTING.md`](docs/HOSTING.md) — running on GitHub Actions
* [`docs/RATE_LIMITS.md`](docs/RATE_LIMITS.md) — Discord + API quotas
* [`docs/FIELDS.md`](docs/FIELDS.md) — full list of widget field names

---

## 📄 License

MIT.
