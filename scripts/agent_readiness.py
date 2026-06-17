#!/usr/bin/env python3
"""Agent / API readiness scorer for OpenAPI specs.

Answers the FloQast question "is this API UI-oriented or agent-ready?" with a
0-100 score and a per-criterion breakdown. Agents perform best when every
operation is uniquely addressable, self-describing, typed, and exemplified, so
they can act from the spec without loading the whole document or guessing.

Usage:
    python3 scripts/agent_readiness.py openapi/core-payments-openapi.yaml
    python3 scripts/agent_readiness.py <spec> --min-score 70   # fail under 70

Writes a Markdown table to $GITHUB_STEP_SUMMARY and `score`/`verdict` to
$GITHUB_OUTPUT when run inside GitHub Actions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required (pip install pyyaml)\n")
    sys.exit(2)

HTTP_METHODS = ("get", "put", "post", "patch", "delete", "options", "head", "trace")


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve(doc: dict, node):
    """Follow a single local $ref ('#/a/b/c'); return node unchanged otherwise."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            break
        target = doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                return node
            target = target[part]
        node = target
        seen += 1
    return node


def operations(doc: dict):
    for path, item in (doc.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        path_params = item.get("parameters", [])
        for method, op in item.items():
            if method.lower() in HTTP_METHODS and isinstance(op, dict):
                yield path, method, op, path_params


def ratio(hits: int, total: int) -> float:
    return 1.0 if total == 0 else hits / total


def score_spec(doc: dict):
    ops = list(operations(doc))
    n = len(ops)

    has_op_id = sum(1 for _, _, op, _ in ops if op.get("operationId"))
    has_docs = sum(1 for _, _, op, _ in ops if op.get("summary") and op.get("description"))

    param_total = param_doc = 0
    success_typed = success_total = 0
    error_doc = 0
    example_hits = 0
    sec_ops = 0

    global_sec = bool(doc.get("security"))

    for _, _, op, path_params in ops:
        params = list(path_params) + list(op.get("parameters", []))
        for p in params:
            p = resolve(doc, p)
            param_total += 1
            if isinstance(p, dict) and p.get("description"):
                param_doc += 1

        responses = op.get("responses", {}) or {}
        codes = [str(c) for c in responses]
        twoxx = [c for c in codes if c.startswith("2")]
        success_total += 1
        if twoxx:
            resp = resolve(doc, responses[twoxx[0]])
            schema = (((resp or {}).get("content") or {}).get("application/json") or {}).get("schema")
            if schema:
                success_typed += 1
            content = ((resp or {}).get("content") or {}).get("application/json") or {}
            if content.get("example") or content.get("examples"):
                example_hits += 1

        if any(c[0] in ("4", "5") for c in codes):
            error_doc += 1

        if global_sec or op.get("security"):
            sec_ops += 1

    prop_total = prop_doc = 0
    for schema in (doc.get("components", {}).get("schemas", {}) or {}).values():
        for prop in (schema.get("properties", {}) or {}).values():
            prop = resolve(doc, prop)
            prop_total += 1
            if isinstance(prop, dict) and prop.get("description"):
                prop_doc += 1

    criteria = [
        ("Unique operationId on every operation", 15, ratio(has_op_id, n)),
        ("Summary + description on every operation", 15, ratio(has_docs, n)),
        ("Every parameter documented", 10, ratio(param_doc, param_total)),
        ("Typed 2xx response schema", 15, ratio(success_typed, success_total)),
        ("Documented 4xx/5xx error responses", 15, ratio(error_doc, n)),
        ("Security applied to every operation", 10, ratio(sec_ops, n)),
        ("Examples on success responses", 10, ratio(example_hits, success_total)),
        ("Schema properties documented", 10, ratio(prop_doc, prop_total)),
    ]

    total = round(sum(weight * cov for _, weight, cov in criteria), 1)
    return total, criteria, n


def verdict(score: float):
    """Return (label, emoji, shields-color) for a score."""
    if score >= 85:
        return "agent-ready", ":green_circle:", "brightgreen"
    if score >= 60:
        return "needs-work", ":large_yellow_circle:", "yellow"
    return "ui-oriented", ":red_circle:", "red"


def bar(cov: float, width: int = 10) -> str:
    filled = round(cov * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="Fail (exit 1) if the score is below this threshold.")
    args = ap.parse_args()

    doc = load(args.spec)
    score, criteria, n = score_spec(doc)
    v, emoji, color = verdict(score)

    # Job-log view (grouped, with a big score bar).
    print("::group::Agent-readiness scorecard")
    print(f"  {bar(score / 100, 20)}  {score}/100  ->  {v}")
    for name, weight, cov in criteria:
        print(f"  {bar(cov)}  {round(cov*100):3d}%  {name}")
    print("::endgroup::")

    badge_score = str(score).replace(".", "%2E")
    lines = [
        "# Agent-Readiness Scorecard",
        "",
        f"![readiness](https://img.shields.io/badge/agent--readiness-{badge_score}%2F100-{color}?style=for-the-badge&logo=robotframework)",
        "",
        f"- **Spec:** `{args.spec}` &middot; {n} operation(s)",
        f"- **Verdict:** {emoji} **{v}** ({score}/100)",
        "",
        "| Criterion | Weight | Coverage | Points |",
        "| :-- | --: | :-- | --: |",
    ]
    for name, weight, cov in criteria:
        lines.append(
            f"| {name} | {weight} | `{bar(cov)}` {round(cov*100)}% | {round(weight * cov, 1)} |"
        )
    lines += [
        "",
        "> Agents act best when every operation is uniquely addressable, self-describing, "
        "typed, secured, and exemplified - so they can act from the spec without loading it whole.",
    ]
    report = "\n".join(lines)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"score={score}\n")
            fh.write(f"verdict={v}\n")

    artifact = {"spec": args.spec, "score": score, "verdict": v,
                "criteria": [{"name": c, "weight": w, "coverage": round(cov, 3)} for c, w, cov in criteria]}
    with open("agent-readiness.json", "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)

    if args.min_score and score < args.min_score:
        sys.stderr.write(f"::error::Agent-readiness score {score} is below threshold {args.min_score}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
