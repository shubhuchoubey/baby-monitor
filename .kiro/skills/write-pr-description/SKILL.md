---
name: write-pr-description
description: Write a pull request description for a branch in this project. Scopes the diff to the correct base branch, fills the repository PR template, and keeps the prose concise and factual.
---

# Write a PR Description

Produce a pull request description for the current branch, using the repository's PR template and the
actual changes on the branch.

Output the description to chat for the human to paste. Do not open the PR, push, or commit.

## Step 1: Determine the base branch

The PR base is **not always `main`**. A branch is often stacked on another unmerged branch.

1. Find the current branch: `git branch --show-current`.
2. List candidate bases and check whether the branch is stacked: `git log --oneline -10 origin/main`
   and `git branch -a`. If the branch's lower commits already belong to another open branch, that
   branch is the base — not `main`.
3. Confirm with the human if the base is ambiguous.

Scope everything below to `<base>..HEAD`, so the description covers only this PR's commits — not commits
inherited from the base.

## Step 2: Read the actual changes

- `git log --oneline <base>..HEAD` — the commits in this PR.
- `git diff --stat <base>..HEAD` — the files touched.
- Read the diffs or the changed files themselves for anything non-obvious. Describe what the code does,
  not what the commit messages say.

## Step 3: Read the template

If the repository defines a PR template (for example `.github/pull_request_template.md`), read it and
fill **every** section it defines, in its order and headings. Do not invent sections or drop the
template's ones. If the repository defines no template, use a concise default structure: what changed,
why, and how it was verified.

## Step 4: Write it

Follow [`references/style.md`](references/style.md). In short: concise and factual, no filler, no AI
slop. Fill `What changed` / `Why did it change` from the diff, cite the relevant ticket reference,
state how it was verified under `Testing` (name the real verification command declared in `AGENTS.md`),
and use `Related Pull Requests` to flag a stacked base branch or companion PRs. Set checklist boxes to
what is actually true; leave a box unticked (with a one-line reason if useful) when it does not apply.

## References

- [`references/style.md`](references/style.md) — writing rules and an annotated example.
