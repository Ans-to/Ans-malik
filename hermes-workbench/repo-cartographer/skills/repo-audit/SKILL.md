---
name: repo-audit
description: "Audit an unfamiliar repository: profile it, find oversized modules, report hotspots."
version: 1.0.0
author: ans-malik/arena
license: MIT
metadata:
  hermes:
    tags: [repository, refactoring, profiling, code-review]
    related_skills: [software-development]
---

# Repository Audit

A short, model-free procedure for answering "what is this codebase and where is
the risk?" Use the `workbench` toolset instead of shelling out to `find`/`wc`.

## When to Use

- You are dropped into an unfamiliar repo and need orientation fast.
- Someone asks where the largest files or refactor targets are.
- You need language mix / LOC numbers for a report or a README.

## When NOT to Use

- Single-file questions → just `read_file`.
- Dependency or vulnerability auditing → use the `security` command instead.

## Steps

1. **Profile it.**
   ```text
   repo_profile(path="<repo root>", top=10)
   ```
   Read back: `files_total`, `megabytes_total`, `languages`, `git.branch`,
   `entry_points_top_level`, `manifests`.

2. **Judge the shape, not just the size.**
   - One language holding >80% of bytes → single-stack repo; depth beats breadth.
   - `git.head` missing but `.git` present → packed-refs only; do not claim a commit id.
   - `scan_truncated: true` → you hit the 200k-file cap; say so in the report.

3. **Find hotspots.**
   ```text
   hotspot_scan(path="<repo root>", loc_limit=800, extensions=".py")
   ```
   The `largest` list is ordered; report the top 5 with line counts.

4. **Read before you judge.** Open the top hotspot with `read_file` before
   calling it a problem — a generated table or a vendored file is not a smell.

5. **Report in the user's units.** Files, MB, LOC, and a one-line verdict.
   No filler, no restating the tool output verbatim.

## Pitfalls

- `repo_profile` skips `.git`, `node_modules`, `__pycache__`, virtualenvs and
  build dirs by design — if the count looks low, that is why.
- Files over 2 MB are counted in totals but not line-scanned, so `loc` can
  under-report for generated or data-heavy repos.
- `hotspot_scan` defaults to `.py` only; pass `extensions` for other stacks.
