# AGENTS.md

Project conventions for the **Raspberry Pi Baby Monitor** POC. This is the tool-neutral source of
project context; the `.kiro` skills defer here, and `CLAUDE.md` points here. When a skill says "see
`AGENTS.md`", the answer is here.

## Project at a glance

- **What it is:** A single Python **Flask** app on a Raspberry Pi 4 that streams live video (MJPEG) and
  audio (WebSocket + Web Audio API) from a USB webcam to a browser on the LAN, with a sound-level
  cry-detection alert. See [`PLAN.md`](plans/PLAN.md) for the phased plan.
- **Runtime:** Python 3 (Raspberry Pi OS 64-bit); Flask, served over the LAN.
- **Status:** Early POC. Conventions below are the intended defaults; refine them as the code grows.

## Module / package structure

The app is a small Python package under `app/`, with tests under `tests/` mirroring it. Keep modules
single-purpose and organised by concern (e.g. `web/`, `video/`, `audio/`, `detection/`), matching the
tasks in [`PLAN.md`](plans/PLAN.md). Conventions:

- **Public interface via `__init__.py`.** A package's `__init__.py` re-exports only what other packages
  should use. Callers import from the package, not its internal modules.
- **One concern per module**, so features can be added incrementally.
- **Wrap hardware/third-party libs behind an internal module** (V4L2/OpenCV, the audio device, etc.) so
  the rest of the app depends on our interface, not the library.
- **Module boundary check (before a module is done):** confirm `__init__.py` exposes only the intended
  interface and that internal helpers / third-party types are not leaking out.

## Verification gate

Run the single gate **once** per phase, after tests are written and code is implemented:

```bash
make verify   # runs, in order: ruff check . | ruff format --check . | mypy app | pytest
```

## Testing conventions

- **TDD.** Write tests before production code for each phase.
- **Mock the hardware.** Camera and microphone I/O must be mocked in unit tests so the suite runs on the
  dev machine (macOS) with no Pi/Brio attached. Reserve real-device checks for manual on-Pi verification,
  noted in the PR's Testing section.
- **Location & naming.** `pytest` under `tests/`, mirroring the `app/` layout; `test_<module>.py`.

## Documentation sync map

Code is the source of truth; docs describe it. When a phase makes one of these changes, update the
listed doc in the same phase, before proposing the commit:

| When you change...                                            | Update...                                                     |
| ------------------------------------------------------------- | ------------------------------------------------------------- |
| The implementation plan or task scope                         | [`PLAN.md`](plans/PLAN.md).                                   |
| Pi provisioning / flashing / SSH / OS setup                   | [`docs/PIE_FLASH_SETUP.md`](docs/PIE_FLASH_SETUP.md).         |
| A user-facing capability or how to run the app                | `README.md`.                                                  |
| A public package interface (a package's `__init__.py`)        | The module's docstrings and any `README.md` usage section.    |
| Runtime/config values (port, resolution, thresholds, systemd) | The relevant runbook under `docs/`.                           |

If a change touches nothing documentation describes, say so rather than guessing.

## Commit and branch conventions

- **Conventional commits.** `type(scope): summary`, e.g. `feat(video): add MJPEG stream endpoint`.
- **Never auto-commit.** Leave each phase committable and propose the message; the human commits.
- **Base branch may not be `main`.** Branches are often stacked; determine the actual base before scoping
  a diff/PR (`git log`, `git branch -a`); confirm if ambiguous. Scope PR descriptions to `<base>..HEAD`.
- **Secrets.** Never commit real credentials. [`docs/PIE_FLASH_SETUP.md`](docs/PIE_FLASH_SETUP.md) keeps
  secrets redacted — follow that pattern.

## Docs & runbooks

Any coding agent should read this file plus the docs below.

- [`PLAN.md`](plans/PLAN.md) — the phased build plan.
- [`docs/PIE_FLASH_SETUP.md`](docs/PIE_FLASH_SETUP.md) — Pi flashing / provisioning (secrets redacted).
- [`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) — deploy / run / monitor / stop and `make verify`.
  Prefer the `scripts/` helpers (`scripts/deploy.sh`, `scripts/start.sh`).
- [`docs/CAMERA_MIC_RUNBOOK.md`](docs/CAMERA_MIC_RUNBOOK.md) — detect & validate the camera/mic
  (`python -m app.detection`). Has a **"revisit when the real IR camera is used"** section — read it
  before changing camera hardware or detection code.

**Runbook policy:** when a new kind of Pi action is done for the first time (new provisioning step,
service, hardware setup), add or update a runbook under `docs/` so it is repeatable.
