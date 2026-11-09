#!/usr/bin/env python3
"""Publishes a local build: the export (`data/explore/`), the passage tables (`data/passage/`) and
the documentation site (`logs/site/`) as assets of a GitHub release of this repo, then starts the
Pages workflow that deploys the site.

The build takes 30-40 min on a GitHub runner and ~5.5 min here, so it runs here and only its result
goes online. defileViz downloads `explore.zip` from the same release when it deploys (its
`scripts/fetch-explore.mjs`); `passage.zip` is the Zenodo upload of the passage tables. Refused: an
export built from a local defile-dataset folder rather than a dataset release, from uncommitted
code, from another commit than HEAD or from a commit not pushed; a `--taxa` build since the last
full one; passage tables or a viewer from another build.

Usage:
    python scripts/publish_explore.py             # to the rolling `dev` pre-release
    python scripts/publish_explore.py --dry-run   # check and zip, upload nothing
    python scripts/publish_explore.py --tag v2025.1
"""

import argparse
import json
import os
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_DIR = os.path.join(ROOT, "data", "explore")
PASSAGE_DIR = os.path.join(ROOT, "data", "passage")
VIEWER_DIR = os.path.join(ROOT, "logs", "site")
ZIP_DIR = os.path.join(ROOT, "logs", "publish")
DEV_TAG = "dev"  # rolling pre-release, until the first versioned release
EXPORT_ASSET = "explore.zip"  # the name defileViz downloads
PASSAGE_ASSET = "passage.zip"  # the passage tables, the Zenodo upload
VIEWER_ASSET = "viewer.zip"  # documentation + QA; the name the Pages workflow downloads
PAGES_WORKFLOW = "pages.yml"
UNCOMMITTED = "uncommitted"


def run(*args: str) -> str:
    return subprocess.run(
        args, capture_output=True, text=True, cwd=ROOT, check=True
    ).stdout.strip()


def check(export_dir: str, passage_dir: str, viewer_dir: str) -> dict:
    """The export's manifest, after the checks that make what goes online traceable to commits."""
    with open(os.path.join(export_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    problems = []
    sha = manifest.get("git_sha") or ""
    if UNCOMMITTED in sha:
        problems.append(f"built from uncommitted code ({sha}): commit, then rebuild")
    elif sha != run("git", "rev-parse", "--short", "HEAD"):
        problems.append(f"built at {sha}, HEAD is elsewhere: rebuild")
    elif not run("git", "branch", "-r", "--contains", "HEAD"):
        problems.append(f"{sha} is not pushed")
    if not manifest.get("dataset_release"):
        problems.append(
            "built from a local defile-dataset folder: release it there"
            " (scripts/release_dataset.py), then build here with --dataset vYYYY.N"
        )
    package = os.path.join(passage_dir, "datapackage.json")
    if not os.path.exists(package):
        problems.append("no passage tables: run a full build")
    else:
        with open(package, encoding="utf-8") as f:
            if json.load(f).get("built_at") != manifest.get("built_at"):
                problems.append("passage tables from another build: run a full build")
    catalogue = os.path.getmtime(os.path.join(export_dir, "taxa.json"))
    species = os.path.join(export_dir, "species")
    if any(os.path.getmtime(os.path.join(species, f)) > catalogue for f in os.listdir(species)):
        problems.append("species files rewritten since the last full build (--taxa): rebuild all")
    viewer = os.path.join(viewer_dir, "index.html")
    if not os.path.exists(viewer) or os.path.getmtime(viewer) < catalogue:
        problems.append("the site is older than the export: run scripts/build_site.py")
    for required in (
        "qa/index.html",
        "qa/compare.html",
        "data/explore/manifest.json",
        "site-manifest.json",
    ):
        if not os.path.exists(os.path.join(viewer_dir, required)):
            problems.append(f"missing {required}: run scripts/build_site.py")
    site_manifest = os.path.join(viewer_dir, "site-manifest.json")
    if os.path.exists(site_manifest):
        with open(site_manifest, encoding="utf-8") as f:
            site = json.load(f)
        if UNCOMMITTED in site.get("site_git_sha", ""):
            problems.append(
                "site built from uncommitted code: commit, then run scripts/build_site.py"
            )
        elif site.get("site_git_sha") != run("git", "rev-parse", "--short", "HEAD"):
            problems.append("site built from another commit: run scripts/build_site.py")
        if site.get("built_at") != manifest.get("built_at"):
            problems.append("site built from another export: run scripts/build_site.py")
    if problems:
        raise SystemExit("Not published:\n  " + "\n  ".join(problems))
    return manifest


def zip_folder(folder: str, path: str) -> str:
    """`folder`'s files at the zip's root."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(folder):
            for f in sorted(files):
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, folder))
    print(f"  {os.path.relpath(path, ROOT)}: {os.path.getsize(path) / 1e6:.1f} MB")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", default=DEV_TAG, help=f"release to publish to (default {DEV_TAG})")
    ap.add_argument("--dry-run", action="store_true", help="check and zip, upload nothing")
    args = ap.parse_args(argv)

    manifest = check(EXPORT_DIR, PASSAGE_DIR, VIEWER_DIR)
    print(f"Export {manifest['git_sha']} of dataset {manifest['dataset_release']}")
    os.makedirs(ZIP_DIR, exist_ok=True)
    assets = [
        zip_folder(EXPORT_DIR, os.path.join(ZIP_DIR, EXPORT_ASSET)),
        zip_folder(PASSAGE_DIR, os.path.join(ZIP_DIR, PASSAGE_ASSET)),
        zip_folder(VIEWER_DIR, os.path.join(ZIP_DIR, VIEWER_ASSET)),
        os.path.join(EXPORT_DIR, "manifest.json"),
    ]
    if args.dry_run:
        print("Dry run: nothing uploaded")
        return 0

    if subprocess.run(
        ["gh", "release", "view", args.tag], capture_output=True, cwd=ROOT
    ).returncode:
        dev = args.tag == DEV_TAG
        run(
            "gh",
            "release",
            "create",
            args.tag,
            "--target",
            run("git", "rev-parse", "HEAD"),
            "--title",
            "Development build" if dev else args.tag,
            "--notes",
            "Local builds, replaced at each publish: manifest.json names the commits."
            if dev
            else f"Explore export {manifest['git_sha']}, dataset {manifest['dataset_release']}.",
            *(["--prerelease"] if dev else []),
        )
    run("gh", "release", "upload", args.tag, *assets, "--clobber")
    print(f"Uploaded to release {args.tag}")
    run("gh", "workflow", "run", PAGES_WORKFLOW, "-f", f"tag={args.tag}")
    print(f"Started {PAGES_WORKFLOW}: the viewer deploys in about a minute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
