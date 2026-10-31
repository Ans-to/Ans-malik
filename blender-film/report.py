#!/usr/bin/env python3
"""Turn a gates report into GitHub check-run annotations.

Everything a CI step prints lives in the job log, and the job log is served from a host that is
not reachable from the machine watching this build. Check-run annotations come back over the
API, so the numbers that matter (every gate's value and verdict) are re-emitted as annotations.

Usage:
    report.py --json out/gates_preview.json --log out/gates_preview.txt [--rc 1]

Exit status is the gates exit status, so the step still goes red when a gate fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# GitHub truncates an annotation message at 64k but the UI shows far less first;
# keep each notice to a readable chunk and split the table over several of them.
CHUNK = 900


def chunks(lines: list[str], size: int) -> list[str]:
    out, cur = [], ""
    for line in lines:
        if cur and len(cur) + len(line) + 2 > size:
            out.append(cur)
            cur = ""
        cur = f"{cur}; {line}" if cur else line
    if cur:
        out.append(cur)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--log", default="")
    ap.add_argument("--rc", type=int, default=0)
    ap.add_argument("--label", default="gates")
    args = ap.parse_args()

    report = None
    if args.json and os.path.exists(args.json):
        try:
            with open(args.json) as fh:
                report = json.load(fh)
        except Exception as exc:  # noqa: BLE001 - a broken report is itself the finding
            print(f"::error title={args.label}::report {args.json} is unreadable: {exc}")

    if report is None:
        print(f"::error title={args.label}::no gates report was written, so nothing was measured")
        if args.log and os.path.exists(args.log):
            with open(args.log, errors="replace") as fh:
                tail = fh.read()[-1200:].replace("\n", "|").replace("\r", "")
            print(f"::error title={args.label} traceback::{tail}")
        return args.rc or 1

    gates = report.get("gates", [])
    passed = report.get("passed_count", sum(1 for g in gates if g.get("pass_")))
    total = report.get("total", len(gates))
    preset = report.get("preset", "")

    failing = [g for g in gates if not g.get("pass_")]
    # Errors first: at most 10 of these survive GitHub's per-step cap, and a failing gate is
    # worth more than a passing one.
    for g in failing[:10]:
        print(
            f"::error title=FAIL {g.get('gate','')}::"
            f"{str(g.get('value',''))[:120]} — {str(g.get('detail',''))[:160]}"
        )
    if len(failing) > 10:
        print(f"::error title=FAIL::{len(failing) - 10} more gates failed; see notices")

    verdict = "PASS" if not failing else "FAIL"
    print(f"::notice title={args.label} {preset} {verdict} {passed}/{total}::"
          + " | ".join(chunks([f"{g.get('gate','')}={str(g.get('value',''))[:60]}" for g in gates], CHUNK)))

    # Also echo the table to the step's own output; harmless when logs are readable.
    for g in gates:
        print(f"[{'PASS' if g.get('pass_') else 'FAIL'}] {g.get('gate',''):<18} {str(g.get('value',''))[:70]:<70} {g.get('detail','')}")
    print(f"\n{passed}/{total} gates passed")

    return 0 if not failing else 1


if __name__ == "__main__":
    sys.exit(main())
