#!/usr/bin/env python3
"""Publish a workspace to the Postman Private API Network (PAN) for discovery.

Idempotent: skips the add if the workspace is already an element in the network.
This is the "discovery" half of FloQast Job 3 - it makes a governed, onboarded
workspace findable by internal teams (and agents) before they build something new.

Usage:
    POSTMAN_API_KEY=PMAK-... python3 scripts/publish_pan.py <workspace-id> [workspace-name]

Writes a short note to $GITHUB_STEP_SUMMARY when run in GitHub Actions.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

API = "https://api.getpostman.com/network/private"


def request(method: str, url: str, key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Api-Key", key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        raise SystemExit(f"::error::PAN request {method} {url} failed: HTTP {e.code} {detail}")


def summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        sys.exit("::error::workspace-id argument is required")
    workspace_id = sys.argv[1].strip()
    workspace_name = sys.argv[2].strip() if len(sys.argv) > 2 else workspace_id

    key = os.environ.get("POSTMAN_API_KEY", "").strip()
    if not key:
        sys.exit("::error::POSTMAN_API_KEY is required")

    existing = request("GET", API, key)
    elements = existing.get("elements", []) if isinstance(existing, dict) else []
    already = any(e.get("type") == "workspace" and e.get("id") == workspace_id for e in elements)

    if already:
        print(f"PAN: workspace {workspace_id} already published - skipping (idempotent).")
        summary(f"- **Private API Network:** `{workspace_name}` already published (idempotent).")
        return 0

    request("POST", API, key, {"workspace": {"id": workspace_id, "parentFolderId": 0}})
    print(f"PAN: published workspace {workspace_name} ({workspace_id}).")
    summary(f"- **Private API Network:** published `{workspace_name}` for internal discovery. :white_check_mark:")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
