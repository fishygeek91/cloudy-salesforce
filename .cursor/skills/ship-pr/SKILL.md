---
name: ship-pr
description: >-
  Create a pull request, review and fix issues, merge it, then switch back to
  main and pull. Use when the user asks to create a PR and merge, ship, close
  and merge, review then merge, or run this project's ship-pr process.
---

# Ship PR

End-to-end ship: open a PR, review/fix, merge, return to `main`.

Never merge unless this skill was invoked or the user explicitly asked to merge in this conversation. Opening a PR alone is not permission to merge.

## 1. Create the PR

Use `gh` for all GitHub work. Do not use TodoWrite or Task for this step.

In parallel:

- `git status`
- `git diff` and `git diff --cached`
- whether the branch tracks a remote and is up to date
- `git log` and `git diff [base]...HEAD` (full history since the branch diverged)

Then, in order:

1. Create a branch if needed.
2. Push with `-u` if the branch is not on the remote.
3. Create the PR:

```bash
gh pr create --title "the pr title" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points>

## Test plan
[Checklist of TODOs for testing the pull request...]

EOF
)"
```

Return the PR URL.

Do not update git config. Do not force-push to main/master.

## 2. Review and fix

Review the PR diff yourself (not only CI).

Fix real bugs, missing tests, and incorrect docs on the feature branch. Commit and push those fixes. Do not commit secrets.

Leave leftover non-blocking work as GitHub issues. Do not pile follow-ups onto `main`.

## 3. Merge

Confirm the PR is mergeable and CI is green (or the user accepted failing checks).

```bash
gh pr merge <N> --merge --delete-branch
```

Use a merge commit unless the repo or human prefers squash/rebase.

## 4. Return to main

Always finish on `main` with a current tree:

```bash
git checkout main
git pull
git fetch --prune
```

Delete the local feature branch if it still exists.

## Do not

- Merge as part of merely opening a PR
- Leave the session on the feature branch after merge
- Commit directly to `main`
- Start the next issue unless asked
