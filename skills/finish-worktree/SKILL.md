---
name: finish-worktree
description: >
  Safely finish a Git worktree after development: inspect changes, invoke the
  commit workflow when needed, decide whether a typed branch should be created
  or the current branch can be used, record merge/publish handoff, and remove
  the worktree only after the working tree is clean and deletion is explicitly
  safe. Use when the user asks to finish, commit, clean up, delete, or remove a
  development worktree.
---

# Finish Worktree

## Overview

Finish a development worktree without losing work or silently publishing code. The process is: inspect Git state, commit via `$commit` if there are changes, preserve merge/publish intent, then remove the linked worktree only when the target path is clean and safe to delete.

## Workflow

### 1. Identify The Worktree

Run these before making changes:

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git worktree list --porcelain
```

Confirm:

- Current path belongs to the worktree the user wants to finish.
- The worktree is linked, not the only checkout or the main coordination checkout.
- The current branch name and target worktree path are known.

If the target is ambiguous, stop and ask for the exact worktree path.

### 2. Commit Pending Changes

If `git status` shows staged, unstaged, or relevant untracked files, invoke `$commit` and follow its rules. In particular:

- Let `$commit` classify the change type from the diff.
- Create a new branch when the current branch is protected (`main`, `master`, `test`, `develop`) or does not match the commit type, unless the user explicitly says to commit on the current branch.
- Stage only relevant files by explicit path. Never use `git add .` or `git add -A`.
- Do not include secrets, local environment files, dependency directories, or unrelated generated artifacts.
- After commit, run `git status --short --branch` again.

If the worktree is already clean, skip commit and keep the existing branch/head as the handoff target.

### 3. Preserve Handoff Before Cleanup

Do not merge, push, or delete a branch as part of worktree cleanup unless the user explicitly requested that operation.

Before removing the worktree, report:

- Branch name.
- Current `HEAD`.
- Whether the branch was committed in this run.
- Whether the branch is already merged, pushed, or only locally available.
- The exact worktree path that will be removed.

For CodeStable repositories, if `.codestable/tools/codestable-finish-worktree.py` exists and the user is finishing an implementation unit, run the project finish gate before cleanup and keep the generated readiness files committed or explicitly handed off. Do not treat `ready-to-merge` as permission to merge.

### 4. Remove The Worktree

Only remove a worktree when all are true:

- `git status --short` is empty in the target worktree.
- The user asked to delete/remove/clean up the worktree, or has confirmed the deletion.
- The branch/head has been committed or the user explicitly accepts deleting an uncommitted-empty worktree.
- You are not relying on the target worktree as the current shell's working directory.

From another checkout or a parent directory, run:

```bash
git -C <main-or-common-checkout> worktree remove <worktree-path>
git -C <main-or-common-checkout> worktree prune
git -C <main-or-common-checkout> worktree list
```

Use `--force` only after a fresh status check proves no useful changes remain and the user explicitly approves force removal.

## Safety Rules

- Do not delete branches automatically. Branch deletion requires a separate explicit request.
- Do not merge automatically. Merge/publish requires owner approval.
- Do not remove a dirty worktree. Commit, stash with explicit approval, or stop.
- Do not infer that a path is safe because its directory name contains `worktree`; verify with `git worktree list --porcelain`.
- If Git reports conflicts, missing refs, detached HEAD, or an untracked secret-like file, stop and report the blocker.
