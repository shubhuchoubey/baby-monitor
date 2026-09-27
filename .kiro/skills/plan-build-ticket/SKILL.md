---
name: plan-build-ticket
description: Generate an implementation approach plan for a build ticket. Splits the ticket into small TDD phases, each independently testable and committable.
---

# Plan a Build Ticket

Generate an implementation approach for the following ticket:

$ARGUMENTS

`$ARGUMENTS` is a file path to the ticket (any text format). Read this file to obtain the ticket content. If the path does not exist or cannot be read, stop immediately and report this to the user rather than proceeding on assumptions or partial information.

---

## Instructions

You are producing an implementation approach document for a ticket in this project. The approach must be output to the chat for review during planning. Do not write the approach document to disk until Step 3 (the interview) has concluded and the plan has been approved — see Step 4.

This skill defers to [`AGENTS.md`](../../../AGENTS.md) for all project mechanics — module/package structure, the verification command, test tooling and locations, and commit conventions. Read it first.

### Step 1: Gather Context

Before planning, gather enough context to plan against the project as it actually is:

1. **Project conventions** — read `AGENTS.md` (the required seam for project mechanics) and `README.md` in the repository root.
2. **Documentation** — if a `docs/` folder is present, read it to understand the project's architecture, testing guides, and any other reference material. If it is absent, skip this and rely on `AGENTS.md` and the source.
3. **Existing source** — explore the project's source tree to understand the current module/package structure, patterns, and what has been implemented. Match what already exists rather than inventing a new layout.
4. **Git history** — run `git log --oneline -40` to understand what work has been completed. Only read commit titles.
5. **Work-package context** — if a broader work-package or design document exists (for example under `context/`), read it to understand how this ticket fits within the larger effort.

### Step 2: Analyse the Ticket

Study the ticket read from the file path in `$ARGUMENTS`. Identify:

- What the ticket requires (functional requirements).
- What is explicitly out of scope.
- What upstream dependencies exist (modules that must exist before this one).
- What downstream consumers will use this module's output.
- What decisions are unresolved (TBDs, ambiguities, open questions).

### Step 3: Interview

Interview the user relentlessly about every aspect of the plan until a shared understanding is reached. Walk down each branch of the design tree, resolving dependencies between decisions one by one.

For every open question:

1. **Explore first.** Check whether the ticket, `AGENTS.md`, the files in `docs/` (if present), any work-package context, or the existing patterns in the source already answer it.
2. **Only ask if unresolved.** If exploration settles the question, state the answer and its source (e.g. "per the existing modules, errors are thrown, not returned as a result value") instead of asking the user to confirm something already established.
3. **Recommend, don't just ask.** For each question actually put to the user, provide a recommended answer based on the ticket, project conventions, and codebase patterns, so the user is confirming or correcting rather than starting from a blank page.

**Group questions by design-tree branch, and ask one group at a time.** Do not dump every open question in a single message. Instead:

- After exploration, cluster the remaining open questions into coherent groups — e.g. "output shape," "error handling convention," "test fixture format," "upstream/downstream interface," "phase boundaries." A group should share a dependency: questions in a later group may depend on answers from an earlier one, but questions within a group should be answerable together without waiting on each other.
- Order the groups so that groups gating the most downstream decisions come first (e.g. resolve the interface/contract shape before asking about test fixtures for that interface).
- Present one group at a time, with each question's recommended answer included. Wait for the user's response before moving to the next group.
- If the user's answer in one group changes the premise of a later group's questions (e.g. an error-handling choice changes what "error path" fixtures look like), revise that later group before presenting it rather than asking the original, now-outdated version.
- Do not proceed to the next group until the current group's questions are resolved, and do not proceed to Step 4 until all groups are resolved.

Do not proceed to Step 4 until all questions are resolved.

### Step 4: Produce the Approach Document

Before producing the approach document, read the following reference files relative to this skill:

- `references/approach-document-template.md` — the output format template to follow exactly
- `references/phase-design-rules.md` — constraints that every phase must satisfy

Once all questions are resolved, produce the approach document following the template and rules from the reference files above.
