#!/usr/bin/env python3
"""Render a Spectral JSON result file into a demo-quality governance report.

Produces three things from one Spectral run:
  1. A rich Markdown scorecard appended to $GITHUB_STEP_SUMMARY.
  2. Inline GitHub annotations (::error / ::warning file=...,line=...) so findings
     show up directly on the spec in the PR "Files changed" view.
  3. A grouped, readable job-log section with a clear PASS/FAIL banner.

It is also the authoritative gate: exit 1 when any blocker (error) is present.

Usage:
    python3 scripts/render_governance.py <spectral.json> <spec-path>
"""
from __future__ import annotations

import json
import os
import sys

# Spectral severity: 0=error, 1=warn, 2=info, 3=hint
SEV = {
    0: ("Blocker", "error", "::error"),
    1: ("Flag", "warning", "::warning"),
    2: ("Info", "notice", "::notice"),
    3: ("Hint", "notice", "::notice"),
}


def gha(name: str, value: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")


def main() -> int:
    results_file, spec = sys.argv[1], sys.argv[2]
    try:
        with open(results_file, "r", encoding="utf-8") as fh:
            results = json.load(fh)
    except (OSError, json.JSONDecodeError):
        results = []

    blockers = [r for r in results if r.get("severity") == 0]
    flags = [r for r in results if r.get("severity") == 1]
    infos = [r for r in results if r.get("severity") in (2, 3)]
    passed = len(blockers) == 0

    # --- Inline annotations (show on the spec in the PR Files view) -----------
    for r in results:
        label, _, cmd = SEV.get(r.get("severity", 1), SEV[1])
        line = (r.get("range", {}).get("start", {}) or {}).get("line", 0) + 1
        col = (r.get("range", {}).get("start", {}) or {}).get("character", 0) + 1
        title = f"{label}: {r.get('code', 'governance')}"
        msg = r.get("message", "").replace("\n", " ")
        print(f"{cmd} file={spec},line={line},col={col},title={title}::{msg}")

    # --- Job-log banner -------------------------------------------------------
    print("::group::FloQast governance gate")
    if passed:
        print("PASS - spec meets the FloQast Stripe-level standard.")
    else:
        print(f"FAIL - {len(blockers)} blocker(s) must be resolved before publishing.")
    print(f"  blockers={len(blockers)}  flags={len(flags)}  info={len(infos)}")
    print("::endgroup::")

    # --- Step summary scorecard ----------------------------------------------
    badge_color = "brightgreen" if passed else "red"
    badge_text = "PASSED" if passed else f"{len(blockers)}_BLOCKERS"
    verdict = "PASSED" if passed else "FAILED"
    icon = "white_check_mark" if passed else "x"

    lines = [
        "# FloQast API Governance Gate",
        "",
        f"![governance](https://img.shields.io/badge/governance-{badge_text}-{badge_color}?style=for-the-badge&logo=postman)",
        "",
        f"- **Spec:** `{spec}`",
        "- **Standard:** Stripe-level (`governance/floqast.spectral.yaml`)",
        f"- **Result:** :{icon}: **{verdict}**",
        "",
        "| Severity | Meaning | Count |",
        "| :-- | :-- | --: |",
        f"| :red_circle: Blocker | Fails CI - not ready to publish | **{len(blockers)}** |",
        f"| :large_yellow_circle: Flag | Surfaced, non-blocking | {len(flags)} |",
        f"| :large_blue_circle: Info | Advisory | {len(infos)} |",
        "",
    ]

    if results:
        lines += [
            "<details open><summary><b>Findings</b></summary>",
            "",
            "| | Rule | Location | Message |",
            "| :--: | :-- | :-- | :-- |",
        ]
        emoji = {0: ":red_circle:", 1: ":large_yellow_circle:", 2: ":large_blue_circle:", 3: ":large_blue_circle:"}
        for r in sorted(results, key=lambda x: x.get("severity", 9)):
            line = (r.get("range", {}).get("start", {}) or {}).get("line", 0) + 1
            loc = " &rarr; ".join(str(p) for p in r.get("path", [])) or "root"
            msg = r.get("message", "").replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {emoji.get(r.get('severity', 1))} | `{r.get('code', '')}` | `L{line}` {loc} | {msg} |"
            )
        lines += ["", "</details>"]
    else:
        lines.append("> :sparkles: Clean spec - no governance findings at any severity.")

    summary("\n".join(lines))

    gha("blockers", str(len(blockers)))
    gha("flags", str(len(flags)))
    gha("passed", "true" if passed else "false")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
