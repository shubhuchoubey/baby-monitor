# PR Description Style

## Rules

- **Concise and factual.** State what changed and why. Cut anything that does not help a reviewer.
- **No AI slop.** No "This PR aims to…", "In order to…", "It's worth noting that…", no restating the
  heading in the first sentence, no summarising the same point twice.
- **Describe the change, not the commits.** Read the diff; say what the code now does. Do not paste or
  paraphrase the commit log.
- **Lead with impact.** If there is no runtime behaviour change (docs, tooling), say so up front.
- **Bullets over paragraphs** for lists of changes; one line each.
- **Name real evidence** under Testing — the exact verification command run (as declared in `AGENTS.md`)
  and what it covered. Do not claim tests that were not run.
- **Checklist honesty.** Tick only what is true. If a box does not apply (e.g. no new logic to unit
  test), leave it unticked; a short reason is fine.
- **Scope.** Cover only `<base>..HEAD`. If commits inherited from a stacked base branch appear in the
  diff, exclude them and note the base under Related Pull Requests.

## Annotated example (docs/tooling PR)

```markdown
## Proposed changes

### What changed

Documentation and tooling only — no runtime behaviour change.

- README rewritten as the user-facing guide (install, quick start, error handling).
- Added a `verify` task that runs lint, format check, type/static check, and tests.

### Why did it change

The README is the canonical reference and needs to stand alone; the docs had drifted from the
implementation.

### Issue tracking

- <TICKET-123>

## Testing

The project's verification gate passes. The README quick-start was checked against the public API.

## Checklist

- [x] Changes are backwards compatible
- [ ] There are unit tests for any new logic implemented
- [x] Documentation (e.g. README.md) has been updated

## Related Pull Requests

- Based on <BASE-BRANCH> — merge that first.
```

Why it works: opens with the no-behaviour-change fact, bullets the changes, gives a real reason,
names the verification command, and is honest that there are no new unit tests.
