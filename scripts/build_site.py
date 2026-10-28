#!/usr/bin/env python3
"""Build the illustrated documentation and QA pages from the existing Explore export.

Run `npm ci --prefix website` once, then `uv run python scripts/build_site.py`. The result is
logs/site/, ready for local preview or publication; no models are fitted.

Order matters: prepare optional illustrations, let Vite replace the site directory, then add QA
pages, historical redirects and build provenance. See website/README.md for source ownership.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "logs" / "site"


def main() -> int:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/export_method_data.py")], cwd=ROOT, check=True
    )
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "website", check=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "explore_viewer.py"), "--out", str(SITE / "qa")],
        cwd=ROOT,
        check=True,
    )
    # Keep existing bookmarks to the original viewer's root-level pages working.
    for page in (SITE / "qa").glob("*.html"):
        if page.name == "index.html":
            continue
        (SITE / page.name).write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0;url=qa/{page.name}">'
            f"<title>Explore QA</title><script>location.replace("
            f'{json.dumps("qa/" + page.name)} + location.search + location.hash)</script>'
            f'<a href="qa/{page.name}">Continue to Explore QA</a></html>',
            encoding="utf-8",
        )
    manifest = json.loads((SITE / "data" / "explore" / "manifest.json").read_text())
    manifest["site_git_sha"] = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        manifest["site_git_sha"] += "-uncommitted"
    (SITE / "site-manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    print(f"Documentation and QA -> {SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
