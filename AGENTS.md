# AGENTS.md

Project mechanics for the **Raspberry Pi Baby Monitor** POC. The `.kiro` skills
(`plan-build-ticket`, `contribute-to-module`, `write-pr-description`) defer to this file for all
project-specific conventions. This is the single seam: when a skill says "see `AGENTS.md`", the answer
is here.

## Project at a glance

- **What it is:** A single Python **Flask** application running on a Raspberry Pi 4 that streams live
  video (MJPEG) and audio (WebSocket + Web Audio API) from a USB webcam to a browser on the local
  network, with a sound-level cry-detection alert. See [`PLAN.md`](PLAN.md) for the full plan and
  [`PIE_FLASH_SETUP.md`](PIE_FLASH_SETUP.md) for Pi provisioning.
- **Language / runtime:** Python 3 (targeting the version shipped with Raspberry Pi OS 64-bit).
- **Web framework:** Flask, served over the LAN.
- **Status:** Early POC — application code is not yet committed. The conventions below are the intended
  defaults; refine them as the codebase takes shape rather than treating them as immovable.

## Module / package structure

The app is a small Python package. Match this layout as the code grows; keep modules single-purpose and
mirror the tasks in `PLAN.md` (video capture, audio capture, sound detection, web layer).

```
app/
├── __init__.py            # Flask app factory / package entry
├── main.py                # app entry point (create + run the Flask app)
├── video/                 # V4L2/OpenCV capture + MJPEG endpoint
│   ├── __init__.py        # the sub-package's public interface
│   ├── capture.py
│   └── stream.py
├── audio/                 # mic capture + WebSocket streaming
│   ├── __init__.py
│   └── capture.py
├── detection/             # sound-level (RMS) cry detection
│   ├── __init__.py
│   └── sound_level.py
├── web/                   # routes, templates, static assets
│   ├── __init__.py
│   ├── routes.py
│   ├── templates/
│   └── static/
tests/                     # test suite (mirrors the app/ layout)
requirements.txt           # pinned dependencies
```

Structure conventions:

- **Public interface via `__init__.py`.** A package's `__init__.py` re-exports only what other packages
  should use. Callers import from the package, not from its internal modules.
- **One concern per module.** Keep capture, streaming, detection, and the web layer separate so features
  can be added incrementally (as the plan requires).
- **Wrap hardware/third-party libs behind an internal module.** Access to V4L2/OpenCV, the audio device
  (sounddevice/pyaudio), and similar should sit behind a thin internal module so the rest of the app
  depends on our interface, not the library directly.

### Module boundary (final-phase check)

Before a module is done, confirm its `__init__.py` exposes only the intended public interface and that
internal helpers and third-party types are not leaking out of the package.

## Verification command (the gate)

Run the single gate **once** per phase, after tests are written and code is implemented:

```bash
make verify
```

`make verify` is the project's verification gate and runs, in order:

1. **Lint** — `ruff check .`
2. **Format check** — `ruff format --check .`
3. **Type check** — `mypy app`
4. **Tests** — `pytest`

Until a `Makefile` and these tools are wired up, the equivalent commands can be run directly
(`ruff check . && ruff format --check . && mypy app && pytest`). Wiring up `make verify` (and the
`requirements`/dev dependencies it needs) is itself an early build task. If, in a given working tree,
no verification gate exists yet, state that explicitly and skip the verify step rather than inventing a
command.

## Test tooling and locations

| Layer            | Tool     | Location                                                    |
| ---------------- | -------- | ---------------------------------------------------------- |
| Unit tests       | `pytest` | `tests/` mirroring the `app/` package (e.g. `tests/video/test_capture.py`) |
| Integration      | `pytest` | `tests/integration/`                                       |

Testing conventions:

- **TDD.** Write tests before production code for each phase.
- **Mock the hardware.** Camera and microphone I/O must be mocked/faked in unit tests so the suite runs
  on the dev machine (macOS) without a Pi or a Brio attached. Reserve real-device checks for manual
  on-Pi verification, noted in the PR's Testing section.
- **Test file naming.** `test_<module>.py`, placed to mirror the module under test.

## Documentation sync map

Code is the source of truth; docs describe it. When a phase makes one of these changes, update the
listed documentation in the same phase, before proposing the commit:

| When you change...                                          | Update...                                                        |
| ----------------------------------------------------------- | ---------------------------------------------------------------- |
| The implementation plan or task scope                       | [`PLAN.md`](PLAN.md) — keep the task breakdown in sync.          |
| Pi provisioning / flashing / SSH / OS setup                 | [`PIE_FLASH_SETUP.md`](PIE_FLASH_SETUP.md).                      |
| A user-facing capability or how to run the app              | `README.md` (add one when the app becomes runnable).             |
| A public package interface (a package's `__init__.py`)      | The module's docstrings and any `README.md` usage section.      |
| Runtime/config values (port, resolution, thresholds, systemd) | The relevant setup doc and any config reference.               |

If a change touches nothing documentation describes, say so explicitly rather than guessing.

## Commit and branch conventions

- **Conventional commits.** `type(scope): summary`, e.g. `feat(video): add MJPEG stream endpoint`,
  `test(detection): cover RMS threshold hysteresis`, `docs: document night-vision upgrade path`.
- **Never auto-commit.** Leave each phase committable and propose the commit message; the human reviews
  and commits.
- **Base branch may not be `main`.** Branches are often stacked on another unmerged branch. Determine the
  actual base before scoping a diff or a PR (`git log`, `git branch -a`); confirm with the human if
  ambiguous. Scope PR descriptions to `<base>..HEAD`.
- **Secrets.** Never commit real credentials (WiFi keys, passwords, SSH private keys). `PIE_FLASH_SETUP.md`
  keeps secrets redacted — follow that pattern.
