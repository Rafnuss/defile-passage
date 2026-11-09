#!/usr/bin/env python3
"""Build the illustrated documentation and QA pages from the existing Explore export.

Run `npm ci --prefix website` once, then `uv run python scripts/build_site.py`. The result is
output/site/, ready for local preview or publication; no models are fitted.

Order matters: prepare optional illustrations, let Vite replace the site directory, then add the QA
and comparison pages, historical redirects and build provenance. See website/README.md for source
ownership.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "output" / "site"


def redirect(page: Path, target: str) -> None:
    """A page that forwards to `target` (relative to it), keeping the query and the anchor."""
    page.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={target}">'
        f"<title>Explore</title><script>location.replace("
        f"{json.dumps(target)} + location.search + location.hash)</script>"
        f'<a href="{target}">Continue</a></html>',
        encoding="utf-8",
    )


def main() -> int:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/export_method_data.py")], cwd=ROOT, check=True
    )
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "website", check=True)
    for script, out in (("explore_viewer.py", "qa"), ("species_compare.py", "compare")):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--out", str(SITE / out)],
            cwd=ROOT,
            check=True,
        )
    # Keep existing bookmarks working: the original viewer's root-level pages, and the
    # comparison's earlier URLs (root, then under qa/).
    for page in (SITE / "qa").glob("*.html"):
        if page.name != "index.html":
            redirect(SITE / page.name, f"qa/{page.name}")
    redirect(SITE / "compare.html", "compare/index.html")
    redirect(SITE / "qa" / "compare.html", "../compare/index.html")
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
