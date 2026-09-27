# Documentation Sync Map

Documentation travels with code: a change is not finished until the docs it affects match. When a phase
changes behaviour, an interface, or a rule that documentation describes, update the corresponding
documentation in the same phase, before proposing the commit.

The specific change → doc mappings for this project (which kind of change obliges which doc update) are
defined in [`AGENTS.md`](../../../../AGENTS.md). Consult it and apply the mappings the change triggers.

Principles:

- **Code is the ultimate source of truth** — docs describe it, they do not lead it.
- **Single source per fact** — where a document is the master copy of a rule or reference, do not
  duplicate its content elsewhere; summarise and link instead.
- **Public surface changes are documented** — when a change alters the module's public interface, update
  the interface documentation and any user-facing entry point (e.g. the README) as `AGENTS.md` directs.
- **Explicit "no doc change"** — if a change touches nothing documentation describes, and `AGENTS.md`
  defines no mapping for it, say so explicitly rather than guessing. If the project defines no doc-sync
  mappings at all, state that and move on.
