# Approach Document Template

Write the approach document to disk at `context/<ticket-id>-approach.md` (create the `context/` directory if it does not exist) and also output it to chat for review, using the format below.

This file is a **living document**, not a one-shot artifact:

- The `Progress` table's `Status` column must be updated as each phase is completed (e.g. ⬜ → 🟩), and the file re-saved, so the plan reflects real state across sessions.
- Updating the status column is part of the per-phase verification flow (see Principles), not a separate manual step to remember later.

---

## Template

````markdown
# <Ticket Title> — Implementation Approach

## Summary

<One paragraph describing what this module does, what it accepts, what it produces, and where it fits in the architecture.>

## Principles

- **TDD** — tests are written before production code at every step.
- **Phased** — each phase is a logical, self-contained unit of work that delivers one testable chunk of the ticket.
- **Verification** — each phase ends by running the project's single verification gate once, as defined in `AGENTS.md`, if one exists. If none is defined, state that and skip.
- **Committable, but never commit** — leave each phase committable with a proposed conventional commit message; never execute or propose to execute the commit command (see `AGENTS.md`).
- **Context check** — before starting each phase, read the commits on the current branch (`git log --oneline <base>..HEAD`, where `<base>` may not be `main`) to understand what work has already been completed.
- **Progress tracking** — after each phase, update the `Status` column in the `Progress` table below and re-save this file.

---

## Progress

Update as each phase is done

| Phase | Description           | Status | Notes |
| ----- | --------------------- | ------ | ----- |
| 1     | <phase 1 description> | ⬜     |       |
| 2     | <phase 2 description> | ⬜     |       |
| ...   | ...                   | ⬜     |       |

---

## Upstream Dependencies

<List modules that must exist before this one can be built. Note any coordination points.>

## Downstream Consumers

<List modules that will consume this module's output. Note the expected interface shape.>

---

## Phase 1: <Title>

### Setup

<Directory and file creation instructions if this is the first phase.>

### Tests (written first)

<Bullet list of test cases to write before implementation.>

### Implementation

<Numbered steps describing what to implement to make the tests pass.>

### Proposed commit (do not execute)

`<conventional commit message>`

---

## Phase N: <Title>

<Same structure as Phase 1 for each subsequent phase.>

---

## Testing Strategy

| Layer      | Tool                    | Location                    |
| ---------- | ----------------------- | --------------------------- |
| <test tier> | <per `AGENTS.md`>       | <per `AGENTS.md`>           |

<Draw the test tiers, tools, and locations from `AGENTS.md`. Add notes on test approach, mocking strategy, and coverage expectations.>

---

## File Structure (final)

```md
<module>/
├── <public entry point>
├── <implementation file>
├── <co-located test>
└── <sub-module or helpers>/
    ├── <file>
    └── <co-located test>
```

<Match the project's existing structure conventions as described in `AGENTS.md`.>
````

---

## Design Decisions

| Decision   | Rationale |
| ---------- | --------- |
| <decision> | <why>     |
| ...        | ...       |
