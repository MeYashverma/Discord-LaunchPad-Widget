# Setup Guide

Step-by-step instructions to get the widget running from scratch.

## Prerequisites

- A GitHub account
- A Discord account
- About 15 minutes

## Step 1 — Create a Discord Application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** in the top right.
3. Name it `LaunchPad` (or whatever you like).
4. Accept the terms of service.

You'll land on the **General Information** page. Note down the
**Application ID** — you'll need it later.

## Step 2 — Create the Widget

In the left sidebar of the Developer Portal:

1. Click **Activities** (you may need to scroll down — it's in the
   settings group).
2. Look for the **Profile Widget** section and click **Enable**.

The widget editor opens. You'll see two tabs: **Widget Top** and
**Widget Bottom**.

### Configure Widget Top

Click on **Widget Top → Content**. Create 5 fields with these
**exact** names and types:

| # | Name | Type |
| - | --- | ---- |
| 1 | `Image` | Image |
| 2 | `Title` | Text |
| 3 | `Subtitle 1` | Text |
| 4 | `Subtitle 2` | Text |
| 5 | `Subtitle 3` | Text |

> ⚠️ Field names are case-sensitive. The widget will not bind to fields
> named `mission` (lowercase) differently from `Mission` (capital M).
> Always use the exact names from this table.

### Configure Widget Bottom

Click on **Widget Bottom → Content**. Create 14 fields:

| # | Name | Type |
| - | --- | ---- |
| 1 | `mission` | Text |
| 2 | `rocket` | Text |
| 3 | `provider` | Text |
| 4 | `status` | Text |
| 5 | `countdown` | Text |
| 6 | `window` | Text |
| 7 | `site` | Text |
| 8 | `location` | Text |
| 9 | `country` | Text |
| 10 | `orbit` | Text |
| 11 | `crew` | Text |
| 12 | `type` | Text |
| 13 | `probability` | Number |
| 14 | `image` | Image |

Click **Save** in the editor.

## Step 3 — Create a Bot

In the left sidebar:

1. Click **Bot**.
2. Click **Add Bot → Yes, do it**.
3. Under **Token**, click **Reset Token** → confirm.
4. **Copy the token** and store it somewhere safe (you'll add it to
   GitHub Secrets in step 6). You won't be able to see this token
   again without resetting it.

## Step 4 — Invite the Bot to Your Server

In the left sidebar:

1. Click **OAuth2 → URL Generator**.
2. Under **Scopes**, check **`bot`**.
3. Under **Bot Permissions**, check:
   - View Channels
   - Send Messages
   - Attach Files
   - Read Message History
4. Scroll down and copy the **Generated URL**.
5. Paste it into your browser, select your server, click **Authorize**.
6. Complete the CAPTCHA.

The bot will now appear in your server's member list (offline, since
we don't keep it running locally).

## Step 5 — Get Your User ID

1. In Discord, click the **⚙️ gear icon** next to your avatar.
2. Go to **Advanced** → enable **Developer Mode** → close settings.
3. **Right-click your own avatar** in any chat → **Copy User ID**.

## Step 6 — Create the Image Upload Channel (Optional)

This is needed if you want the `Image` field to display. Without this
step, the widget's image slot will be empty.

1. In your Discord server, create a new channel: **`#launchpad-assets`**
   (private is fine, only you and the bot need access).
2. Right-click the channel → **Edit Channel** → **Permissions**.
3. Click **+ Add members or roles** → search for your bot → add it.
4. Toggle **ON** for the bot: `View Channel`, `Send Messages`, `Attach Files`.
5. Right-click the channel header → **Copy Channel ID** (you may need
   to enable Developer Mode first, see Step 5).

## Step 7 — Add Secrets to GitHub

In your fork of the repo:

1. Go to **Settings → Secrets and variables → Actions → Secrets tab**.
2. Click **New repository secret** for each:

   | Name | Value |
   | --- | --- |
   | `DISCORD_APPLICATION_ID` | The Application ID from Step 1 |
   | `DISCORD_USER_ID` | The User ID from Step 5 |
   | `DISCORD_BOT_TOKEN` | The Bot token from Step 3 |
   | `DISCORD_TARGET_CHANNEL_ID` | (Optional) The channel ID from Step 6 |

**Important:** These go in **Secrets**, not Variables. Secrets are
encrypted; Variables are visible to anyone with read access.

## Step 8 — Run the Workflow

1. Go to the **Actions** tab in your repo.
2. Click **Update LaunchPad Widget** in the left sidebar.
3. Click **Run workflow → Run workflow**.

The first run will:
- Install Python dependencies (`requests`, `Pillow`)
- Start the daemon
- Fetch the next launch
- PATCH the widget

You should see the widget populate on your Discord profile within a
minute or two. The daemon will keep running and self-dispatch new
runs as needed.

## Troubleshooting

### Widget shows field names but no values

Your widget editor field names don't match the daemon's. Open the editor
and check each field's Name exactly.

### Widget shows the widget shell but no data at all

The PATCH might be failing silently. Check the workflow logs for errors.

### Image slot is empty

You didn't create `DISCORD_TARGET_CHANNEL_ID` as a Secret, or the bot
lacks permissions in the channel.

### 401 / Unauthorized errors in the logs

The bot token was rotated. Reset it in the Developer Portal and update
the `DISCORD_BOT_TOKEN` Secret.

### Widget updates then stops

The daemon's runtime budget elapsed. It will be re-triggered by the 6h
`schedule:` cron. To reduce the gap, run the workflow manually.

## Next steps

- Read [HOSTING.md](HOSTING.md) to understand the GitHub Actions daemon
- Read [RATE_LIMITS.md](RATE_LIMITS.md) to understand quota math
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for module-level design
