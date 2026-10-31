# Contributing to DeskBuddy

Thanks for your interest! Bug reports, fixes, new pets and docs are all welcome.

## Setup

```bash
scripts/setup.sh   # once: system packages, Rust (rustup), Node, npm packages
scripts/run.sh     # build and launch a debug build
```

You need Rust 1.85+ from [rustup](https://rustup.rs) (Ubuntu's packaged cargo is too old) and Node 20.19+.

## Before opening a pull request

```bash
(cd src-tauri && cargo test)   # Rust unit tests (crypto, vault, backups, todos, alarms, throw physics…)
npm test                       # pet state machine (hover, body parts, throws, sleep) + every pet pack's data
npm run build                  # type-check + frontend build
```

- Keep pull requests focused: one fix or feature each.
- Match the style of the surrounding code.
- If you change behaviour, update [README.md](README.md) (or [assets/PETS.md](assets/PETS.md) for pets).
- Never commit secrets, `.env` files or `*.db` files; `.gitignore` already excludes them.

## Adding a pet

Each pet is a folder in `assets/` with a `mascot.json` that maps events to clips; see [assets/PETS.md](assets/PETS.md). Run `python3 scripts/prepare-pets.py` after adding or regenerating a pack. Only contribute artwork you made yourself or whose license allows redistribution, and say where it came from in the pack's `README.md`.

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
