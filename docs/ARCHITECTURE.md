# Architecture

This document describes the runtime architecture, request lifecycle,
and module-level design of the Discord LaunchPad Widget daemon.

## High-level overview

```mermaid
graph TB
    subgraph Cloud[GitHub Actions runner]
        GHA[Workflow trigger]
        PY[widget.py entry]
        ORC[WidgetOrchestrator]
        PVD[LaunchProvider x2]
        IMG[ImageService]
        DWIF[DWIF runner]
        PAY[PayloadBuilder]
        UP[DiscordUpdater]
    end

    subgraph External[External services]
        LL2[Launch Library 2]
        SX[SpaceX API]
        CDN[Discord CDN]
    end

    subgraph Discord[Discord platform]
        CHN[Your private channel]
        WID[Profile widget]
    end

    GHA --> PY --> ORC
    ORC --> PVD
    PVD -.HTTP.-> LL2
    PVD -.HTTP.-> SX
    ORC --> IMG
    IMG --> DWIF
    DWIF -->|styled PNG| UP
    ORC --> PAY
    PAY --> UP
    UP -.multipart POST.-> CHN
    CHN -.returns.-> CDN
    UP -.PATCH.-> WID
    WID -.uses.-> CDN
```

## Request lifecycle

A single daemon cycle has these stages:

```mermaid
sequenceDiagram
    autonumber
    participant ORC as Orchestrator
    participant PVD as Provider
    participant IMG as ImageService
    participant DWIF as DWIF runner
    participant UPL as ImageUploader
    participant PAY as PayloadBuilder
    participant UPD as DiscordUpdater
    participant API as Discord API

    ORC->>PVD: next_launches(limit=5)
    PVD-->>ORC: list[Launch]
    ORC->>ORC: pick earliest with future NET
    ORC->>IMG: best_image_for(launch)
    IMG-->>ORC: {source, local_path}
    ORC->>DWIF: process_image(local_path)
    DWIF-->>ORC: styled PNG path
    ORC->>UPL: upload(styled_png)
    UPL->>API: POST /channels/{id}/messages
    API-->>UPL: {attachments: [{url: cdn.discordapp.com/...}]}
    UPL-->>ORC: cdn_url
    ORC->>PAY: build(launch, image_info)
    PAY-->>ORC: {username, data: {dynamic: [...]}}
    ORC->>UPD: push(payload)
    UPD->>API: PATCH /identities/0/profile
    API-->>UPD: 204
    UPD-->>ORC: True
    ORC->>ORC: sleep UPDATE_INTERVAL_SECONDS
```

## Concurrency model

The daemon is single-threaded. All API calls and image processing are
sequential. This is intentional:

- Discord's PATCH endpoint is rate-limited (~3 per bucket); concurrent
  PATCHes would burn the budget faster.
- Image processing is sub-second per image; no need for parallelism.
- The cycle interval (default 5 min) is the throughput ceiling.

If higher throughput is ever needed, the orchestrator's `cycle()` can
be wrapped in a `concurrent.futures.ThreadPoolExecutor` since the only
blocking calls (HTTP) are I/O-bound.

## Lifecycle of a daemon run

```mermaid
stateDiagram-v2
    [*] --> Starting
    Starting --> Configuring: validate env
    Configuring --> CycleLoop: providers ready
    Configuring --> FatalError: missing config

    CycleLoop --> Sleeping: cycle done
    Sleeping --> CycleLoop: interval elapsed
    Sleeping --> BudgetExhausted: runtime > MAX_RUNTIME_SECONDS
    Sleeping --> Stopped: SIGINT / SIGTERM

    CycleLoop --> CycleLoop: throttled by MIN_PATCH_INTERVAL
    CycleLoop --> CycleLoop: provider error → fall back

    BudgetExhausted --> [*]: clean exit (rc 0)
    Stopped --> [*]: clean exit (rc 0)
    FatalError --> [*]: exit (rc 2)
```

## Module dependencies

```mermaid
graph LR
    main[main.py] --> cfg[config.py]
    main --> orch[services/orchestrator.py]
    main --> log[utils/logging_setup.py]

    orch --> ll2[apis/launch_library.py]
    orch --> sx[apis/spacex.py]
    orch --> imgsvc[services/image_service.py]
    orch --> dwifsvc[services/dwif_runner.py]
    orch --> payload[services/payload_builder.py]
    orch --> updater[services/discord_updater.py]
    orch --> http[utils/http_client.py]
    orch --> cache[utils/cache.py]

    ll2 --> http
    sx --> http
    imgsvc --> http
    imgsvc --> cache
    payload --> models[models.py]
    updater --> http
    http --> retry[utils/retry.py]
    dwifsvc --> stdlibPIL[Pillow]
```

## Data flow

```mermaid
flowchart LR
    subgraph Inputs
        LL2[LL2 JSON]
        SX[SpaceX JSON]
        IMG_BYTES[Image bytes]
    end

    subgraph Normalisation
        M[Launch dataclass]
    end

    subgraph Selection
        PK[Pick earliest valid]
    end

    subgraph Output
        P[Discord identities JSON]
    end

    LL2 --> M
    SX --> M
    M --> PK
    PK --> P
    IMG_BYTES -->|via DWIF| P
```

## Error handling strategy

| Failure | Behaviour |
| --- | --- |
| LL2 unreachable | Try SpaceX provider instead |
| Both providers fail | Log warning, skip cycle, retry next tick |
| No image for launch | Use bundled fallback image |
| D.W.I.F fails | Log warning, use raw image |
| Image upload 401 | Retry once after 2s (transient Discord rate limit) |
| Image upload 403 | Skip image, still PATCH text fields |
| PATCH 429 | Honour `Retry-After`, raise to caller |
| PATCH 4xx | Log error, continue to next cycle |
| PATCH 5xx | Retry with backoff |
| Workflow runner SIGKILL'd | 6h `schedule:` cron re-runs the workflow |

## File system layout

```
/home/runner/work/.../             <- GitHub Actions checkout
├── widget.py                       <- entry point
├── launchpad_widget/               <- package
│   ├── main.py                     <- package entry
│   ├── config.py                   <- env / config.json loading
│   ├── models.py                   <- dataclasses (Launch, CrewMember)
│   ├── apis/
│   │   ├── base.py                 <- LaunchProvider Protocol
│   │   ├── launch_library.py        <- LL2 client + parser
│   │   └── spacex.py               <- r-spacex client + parser
│   ├── services/
│   │   ├── image_service.py        <- image picker + cache
│   │   ├── dwif_runner.py          <- D.W.I.F image styling
│   │   ├── payload_builder.py       <- Launch → Discord JSON
│   │   ├── discord_updater.py      <- PATCH + state dedup
│   │   └── orchestrator.py         <- main loop
│   ├── utils/
│   │   ├── http_client.py          <- requests wrapper + retry
│   │   ├── cache.py                <- TTL caches (API + image)
│   │   ├── retry.py                <- generic backoff helper
│   │   └── logging_setup.py        <- rotating file + console
│   └── assets/
│       └── fallback.png             <- bundled fallback image
├── cache/                          <- runtime artefacts (gitignored)
│   ├── launches.json               <- API response cache
│   ├── last_payload.json           <- dedup state
│   └── images/                     <- downloaded launch images
├── dwif/                           <- D.W.I.F install (gitignored, optional)
├── config.json                     <- local override (gitignored)
├── widget.log                      <- runtime log (gitignored)
└── .github/workflows/update.yml    <- CI daemon
```

The `cache/` and `dwif/` directories are not committed — they're
runtime artefacts that are regenerated on each run.
