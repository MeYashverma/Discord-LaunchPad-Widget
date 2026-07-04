# 🚀 Discord LaunchPad Widget

> **Live space-launch tracker → Discord profile widget.**
> Periodically fetches the next scheduled rocket launch from free public APIs,
> transforms the data into Discord's Dynamic Identity JSON, and PATCHes your
> profile widget — no PC, no VPS, no frontend.

```
No VPS             No Paid APIs        No Local Machine
No Manual Updates  No Frontend         100% Cloud Automated
```

---

## What this is

A cloud daemon (designed to run as a long-lived GitHub Actions job) that
keeps your Discord profile widget in sync with the **next scheduled space
launch**. Every few minutes it:

1. Fetches upcoming launches from **Launch Library 2** and the **SpaceX API**.
2. Normalises the data onto a single `Launch` shape.
3. Picks the best available image (rocket > mission patch > artwork > pad).
4. Optionally uploads the image to a Discord channel to get a CDN URL.
5. Builds a Discord Dynamic Identity JSON payload (top + bottom identities).
6. PATCHes the widget through Discord's official endpoint.
7. Loops, with a graceful exit before the runner's hard timeout.

This is **not** a website, **not** a dashboard, and **not** a frontend
application. The only output is the JSON payload sent to Discord and the
image asset used to populate the widget.

---

## Widget layout

The Discord profile widget has two sections, both populated by the daemon:

### Widget Top
- `Image` — rocket or mission patch
- `Title` — mission name
- `Subtitle 1` — rocket + provider
- `Subtitle 2` — countdown
- `Subtitle 3` — launch site + location

### Widget Bottom (stats)
- `mission`, `rocket`, `provider`, `status`, `countdown`, `window`
- `site`, `location`, `country`, `orbit`, `crew`, `type`
- `probability` (number)
- `image` (image)

Field names must match the Data Field names in your Discord widget editor
**exactly** (case-sensitive).

---

## Data sources

| Source | Used for |
| --- | --- |
| [Launch Library 2](https://thespacedevs.com/llapi) | Primary — covers every operator |
| [SpaceX API](https://github.com/r-spacex/SpaceX-API) | Secondary — SpaceX in detail |

Both are free, no auth, plenty of rate limit for this use case.

## Image processing (D.W.I.F)

The widget image is processed through [D.W.I.F](https://github.com/AjaxFNC-YT/D.W.I.F)
(Discord Widget Image Fixer) before being uploaded. The full pipeline:

1. **Download** the best available launch image (rocket artwork → mission
   patch → launch artwork → launchpad image) to a local cache.
2. **Center-crop + resize** the image to a 1300×1300 square PNG using
   Pillow. This makes the artwork fill Discord's square widget canvas
   instead of sitting tiny in the middle of a wide frame.
3. **D.W.I.F** adds a transparent top strip (~57px at 1300x1300) and a
   rounded top-right corner so the image clips correctly into Discord's
   widget rounded rectangle.
4. **Upload** the styled PNG to your Discord channel via the bot.
5. **PATCH** the widget with the resulting `cdn.discordapp.com` URL.

The daemon handles the D.W.I.F install automatically on first run:

1. Detects Node.js (set up in the workflow via `actions/setup-node`)
2. Clones D.W.I.F into `./dwif/`
3. Runs `npm install --omit=dev` to install dependencies
4. Runs the full D.W.I.F pipeline on every picked launch image

If Node.js or D.W.I.F are unavailable, the daemon gracefully falls back
to uploading the raw image (still works, just without the rounded
corner / top strip and without the square pre-resize).

**Output size:** the daemon produces 1300×1300 + strip = ~1300×1357 px
PNG images.  Discord scales them to fit the 650×650 base widget canvas,
which is 2x resolution — crisp on all displays.

---

## Setup

### 1. Create a Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** (e.g. "LaunchPad").
3. Open **Activities → Profile Widget → Enable**.

### 2. Create the data fields

The widget editor has two tabs: **Widget Top** and **Widget Bottom**.

**Widget Top → Content** — add 5 fields with these exact names:
| Name | Type |
| --- | --- |
| `Image` | Image |
| `Title` | Text |
| `Subtitle 1` | Text |
| `Subtitle 2` | Text |
| `Subtitle 3` | Text |

**Widget Bottom → Content** — add 14 fields with these exact names:
| Name | Type | Name | Type |
| --- | --- | --- | --- |
| `mission` | text | `location` | text |
| `rocket` | text | `country` | text |
| `provider` | text | `orbit` | text |
| `status` | text | `crew` | text |
| `countdown` | text | `type` | text |
| `window` | text | `probability` | number |
| `site` | text | `image` | image |

⚠️ **Names are case-sensitive.** If you type `Mission` instead of `mission`,
the field will not bind.

### 3. Create a bot

In the Developer Portal:
- **Bot → Add Bot** → copy the token → save it as `DISCORD_BOT_TOKEN`.

### 4. Invite the bot

OAuth2 → URL Generator:
- Scopes: `bot`
- Permissions: `Send Messages`, `Attach Files`, `Read Message History`, `View Channels`
- Copy the URL, open it, authorize in your server.

### 5. Collect IDs

- **Application ID** (Developer Portal → General Information) → `DISCORD_APPLICATION_ID`
- **User ID** (Discord → right-click your avatar with Developer Mode on) → `DISCORD_USER_ID`

### 6. (Optional) Image upload channel

1. Create a private channel in your server (e.g. `#launchpad-assets`).
2. Add the bot to that channel with Send + Attach permissions.
3. Right-click the channel → Copy Channel ID → save as `DISCORD_TARGET_CHANNEL_ID`.

If you skip this step, the widget's `Image` field will be empty (Discord
can't render `file://` URLs).

### 7. Add GitHub Secrets

In your repo: **Settings → Secrets and variables → Actions → Secrets**:
- `DISCORD_APPLICATION_ID`
- `DISCORD_USER_ID`
- `DISCORD_BOT_TOKEN`
- `DISCORD_TARGET_CHANNEL_ID` (optional)

(Variables, not Secrets, for tunables like `UPDATE_INTERVAL_SECONDS`.)

### 8. Run the workflow

**Actions → Update LaunchPad Widget → Run workflow.**

---

## Local testing

```bash
pip install -r requirements.txt
cp config.example.json config.json
# fill in creds
DRY_RUN=true python widget.py
```

`DRY_RUN=true` logs the payload without PATCHing Discord.

---

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `PREFERRED_SOURCE` | `launch_library` | `launch_library` or `spacex` |
| `UPDATE_INTERVAL_SECONDS` | `300` | Time between cycles |
| `MIN_PATCH_INTERVAL_SECONDS` | `60` | Throttle for Discord PATCHes |
| `MAX_RUNTIME_SECONDS` | `21000` | Soft runtime budget (loop exits cleanly) |
| `CACHE_TTL_SECONDS` | `120` | API response cache |
| `DRY_RUN` | `false` | Log payload, don't PATCH |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Project layout

```
launchpad_widget/
├── apis/                    # LL2 + SpaceX providers
├── services/                # image, payload, discord updater, orchestrator
├── utils/                   # cache, http client, retry, logging
├── assets/fallback.png
├── config.py
├── models.py
└── main.py
```

---

## License

MIT.
