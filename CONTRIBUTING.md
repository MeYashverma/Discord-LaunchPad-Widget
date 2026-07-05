# Contributing

Contributions are welcome! This is a personal project but I'm happy
to accept PRs for bug fixes, new data sources, and improvements.

## How to contribute

1. **Fork** the repository
2. **Create a feature branch** (`git checkout -b feature/my-change`)
3. **Make your changes**
4. **Test locally** with `DRY_RUN=true python widget.py`
5. **Commit** with a clear message
6. **Push** to your fork
7. **Open a Pull Request** with a description of what changed and why

## Code style

- **Python 3.11+** syntax (match expressions, `|` for unions, etc.)
- **Type hints** for all public functions
- **Docstrings** for modules and public classes
- **No external dependencies** beyond `requests` and `Pillow`
- **Keep it small** — the daemon runs in a 6h window; every cycle should
  finish in <30s

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add NASA APOD enrichment
fix: handle LL2 image dict response
docs: add architecture diagram
chore: bump Pillow to 10.4
```

## Reporting bugs

Open a [GitHub Issue](https://github.com/MeYashverma/Discord-LaunchPad-Widget/issues)
with:

- **What you expected to happen**
- **What actually happened** (with the workflow log if it's a daemon bug)
- **Steps to reproduce** (config used, launch that triggered it, etc.)
- **Discord widget editor screenshot** if it's a display issue

## Feature requests

Open a [GitHub Discussion](https://github.com/MeYashverma/Discord-LaunchPad-Widget/discussions)
with the `idea` tag. Include:

- The data source or feature you want
- Why it would be useful
- Any sample output / mockup

## Code of conduct

Be kind. We're all here to learn and build cool stuff.

## Security

If you find a security issue (e.g. token leak, RCE in the daemon), please
**do not** open a public issue. Email me directly instead.
