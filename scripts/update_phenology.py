"""Refresh only the derived phenology block in an existing local Explore export.

Daily fits and reconstructions are unchanged. A full committed build is still required to publish.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from defile_passage import reliability as Q
from defile_passage.export import EXPORT_DIR
from defile_passage.phenology import METHOD, phenology_block

ROOT = Path(__file__).resolve().parents[1]


def main():
    export = ROOT / EXPORT_DIR
    for path in (export / "species").glob("*.json"):
        data = json.loads(path.read_text())
        data["season"]["phenology"] = phenology_block(data["season"])
        reliability = data.get("reliability")
        if reliability:
            reliability["elements"]["season.phenology"] = Q.element(
                "season.phenology", reliability["season"]["class"]
            )
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
        )
    path = export / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest.setdefault("base_statistics_git_sha", manifest["git_sha"])
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
    ).strip()
    manifest["git_sha"] = sha + "-uncommitted"
    manifest["phenology_update"] = {
        "method": METHOD,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Refreshed annual-date phenology for all exported taxa; daily fits unchanged.")


if __name__ == "__main__":
    main()
