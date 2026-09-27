# Key Rules for Phase Design

The mechanical conventions an agent must obey while implementing are defined
in [`AGENTS.md`](../../../../AGENTS.md) and are not restated here. This file adds only the rules that shape
how a ticket is split into phases.

1. **Each phase must be logical and self-contained** — a phase delivers one clearly-scoped, testable chunk of the ticket (e.g. one function, one helper, one encoder, one validation concern). There is no fixed phase count or time budget: granularity depends on the nature of the task, and the user will guide how finely to split a given plan during the interview.
2. **Phases build on each other** — later phases may depend on earlier ones, but each is independently testable.
3. **Each phase is TDD and ends with the verification gate** — tests are written first; the phase ends by running the project's single verification gate once (see `AGENTS.md`), then is left committable with a proposed conventional commit message.
4. **The final phase enforces the module boundary** — confirm the module exposes only its intended public interface and hides internals, following the boundary conventions in `AGENTS.md`.
5. **Follow existing patterns** — match the structure, test style, and public-interface conventions of the project's existing modules, as described in `AGENTS.md`.
