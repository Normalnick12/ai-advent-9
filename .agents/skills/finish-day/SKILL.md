---
name: finish-day
description: Finish one implemented and user-verified AI Advent Day by checking its scoped changes, validating and conditionally archiving its OpenSpec change, running only necessary checks, committing, and pushing. Use for requests such as "$finish-day Day 03" after the user has tested the implementation and recorded the video; do not use to implement an unfinished Day.
---

# Finish an AI Advent Day

Finalize exactly one completed Day. Invocation authorizes the normal scoped commit and push described here, but no history rewriting, force push, destructive reset, remote change, or mutation of unrelated work.

## Resolve the Day and scope

1. Read the repository-root `AGENTS.md`, then every more specific `AGENTS.md` applicable to files that may be inspected, changed, tested, staged, or committed. Deeper instructions take precedence within their directory scope.
2. Parse a case-insensitive argument such as `Day 03` or `Day 3`, normalize it to two digits, and find the matching repository-root directory `day-NN-*`.
3. If no Day number was supplied, infer it only when the conversation and working tree identify exactly one Day. Otherwise ask the user; never guess.
4. Require exactly one matching Day directory. If none or more than one matches, stop and report the ambiguity.
5. Scope the finalization to that Day directory plus shared implementation, tests, documentation, and OpenSpec artifacts that clearly belong to it. Preserve all unrelated and user-owned changes. If a shared file mixes relevant and unrelated edits that cannot be staged safely, stop and ask rather than taking the whole file.

The implementation is expected to be complete, user-verified, and already recorded. Do not broaden this workflow into feature development. Small fixes found by the required checks are allowed when they are clearly within the selected Day.

## Inspect Git and protect sensitive/local data

Before changing anything, run `git status` and review the complete relevant working-tree diff. Identify pre-existing or unrelated changes and keep them out of the final commit.

Ensure neither the intended commit nor its staged snapshot contains:

- API keys, access tokens, credentials, or other secrets;
- `.env` files other than intentionally safe examples;
- `.venv`, `venv`, `__pycache__`, or Python bytecode;
- Android or other generated `build/` directories;
- IDE settings, machine-local configuration, temporary files, and user caches;
- an `ast-index` database or cache.

Use ignore checks and secret scanners when available. Inspect findings without echoing secret values. Never reproduce a secret in commentary, command output intentionally constructed by this workflow, a commit message, or the final report. If a real secret may have entered Git history, stop before commit or push and report only its file path and credential type plus the minimum remediation required.

Run `git diff --check`. After all fixes, OpenSpec operations, and README updates, review the final unstaged and staged diffs and run `git diff --check` again.

## Handle a related OpenSpec change

Use `openspec list --json` and the change artifacts to determine whether an active change clearly corresponds to the selected Day. Match using explicit Day references, the Day directory/name, and the current change scope; do not select a change merely because it is the only active change when the relationship is unclear.

- If no related change exists, record OpenSpec as `skipped`.
- If multiple changes could match, ask the user which one belongs to the Day.
- If one related change exists, announce it and run `openspec status --change "<name>" --json`.

For a related change:

1. Read the status-reported artifact paths and task artifact. Require all implementation tasks to be complete and all required artifacts to be done or explicitly skipped.
2. Run strict, non-interactive validation with `openspec validate "<name>" --type change --strict --no-interactive`.
3. If status, tasks, or strict validation are not fully successful, do not archive. Report the exact non-secret reason and continue toward commit only when the remaining Day state is still valid to commit under applicable `AGENTS.md`; otherwise stop.
4. If the change is complete and valid, read and follow the repository-local `openspec-archive-change` skill for the standard archive and spec-sync workflow. The stricter rule here wins: never bypass incomplete artifacts/tasks or failed strict validation, even if the archive workflow offers confirmation.
5. Include the archive and any verified spec synchronization in the same Day commit. Record the archive result and path.

If OpenSpec or its CLI is absent and there is no OpenSpec change for this Day, skip the step. If artifacts show that a related change exists but the required CLI/workflow is unavailable, stop rather than moving change directories manually.

## Reuse or run project checks

Avoid repeating expensive tests, builds, and runtime checks.

- Reuse a successful result only when it is concrete evidence from the current working session, covers the final relevant behavior, and no material affected code or configuration changed afterward.
- If evidence is missing or stale, run the smallest reasonable set of checks for the selected Day and its affected shared modules, following applicable `AGENTS.md` and project documentation.
- When a check finds a real scoped defect, fix it minimally and rerun only the checks affected by that fix.
- If a failure is unrelated, preserve it and report it without modifying unrelated work. Stop if it prevents establishing that the selected Day is safe to commit.

Record each check as either `run` or `reused`, including the command or runtime scenario and its result.

## Verify the Day README

Review the selected Day's `README.md`. It must match the final implementation, explain a clear run scenario, state the key learning takeaway, list required dependencies/environment variables without real secret values, and follow applicable `AGENTS.md`.

Make only necessary, scoped corrections. Do not rewrite an already accurate README for style alone.

## Optionally update ast-index

After final source changes, detect whether `ast-index` is available. If so, `ast-index update` is optional. Never run `ast-index rebuild` in this workflow; it is unnecessary, and a future explicit rebuild request must first account for Windows upstream issue #61. Absence or failure of this optional update does not block Day completion. Never stage its local database or cache.

## Stage, commit, and push safely

1. Stage only explicit paths and hunks required for the selected Day, its affected shared code/tests/docs, and its completed OpenSpec archive/spec sync. Do not use broad staging that captures unrelated files.
2. Inspect `git status`, `git diff --cached --name-status`, and the complete staged diff. Repeat the forbidden-file and secret checks against the index. Run `git diff --cached --check`.
3. Do not create an empty commit. If nothing relevant remains to commit, stop and explain.
4. Create one short, meaningful English commit message that names or clearly describes the completed Day, for example `Complete Day 03 reasoning strategies`.
5. Determine the current branch and its configured upstream. Run a normal `git push` to that upstream. Do not change the remote or invent an upstream silently.

Never run `git push --force`, `git commit --amend`, a destructive reset, history rewriting, or deletion of another person's changes unless the user separately and explicitly requests that exact operation. If commit or push is blocked by authentication, network, sandbox, permissions, missing upstream, or hooks, do not bypass the protection; report the minimum user action needed.

## Verify and report

After a successful push, run `git status`, resolve the new commit hash, current branch, configured upstream, and `origin` URL. Convert an SSH or HTTPS GitHub origin to `https://github.com/<owner>/<repo>` without changing the remote. URL-encode the branch when necessary and form a direct link to the exact selected directory:

`https://github.com/<owner>/<repo>/tree/<branch>/day-NN-short-name`

Do not fabricate a GitHub link when `origin` is not a recognizable GitHub repository.

Keep the final response short and include:

- Day and resolved directory;
- OpenSpec: `archived`, `skipped`, or the reason it was not archived;
- checks run or reused;
- commit message and commit hash;
- branch and push result;
- final Git status, including whether the working tree is clean or only contains preserved unrelated changes;
- the direct GitHub link to the Day directory.
