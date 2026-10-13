"""Run `run_steps.py` as a queue of small jobs, with a cap on the machine's load.

One job per mask set, draw and species, each a single-threaded process (`THREAD_VARS` = 1) at low
priority (`nice`), at most `--workers` at a time (default: a third of the cores, so the computer
stays usable). A job whose outputs already exist is skipped, so a stopped run resumes where it
left off. Each job logs to `<out>/logs/`.

Run from the repository root, e.g. P and D on the realistic masks and the lockbox:
uv run python scripts/hierarchical/run_jobs.py --arms P D --sets masks:steps-stops \
    lockbox:lockbox-steps-stops > logs/hierarchical/jobs.log 2>&1
"""

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import CORE, LOGS, ROOT

THREAD_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
NICE = 10
RUN = [
    "uv",
    "run",
    "--with",
    "pyarrow<20",
    "python",
    "scripts/hierarchical/run_steps.py",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument(
        "--sets", nargs="+", required=True, help="<masks folder>:<out folder>, in logs/hierarchical"
    )
    parser.add_argument("--species", nargs="+", default=list(CORE))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) // 3))
    args = parser.parse_args()
    env = os.environ | {var: "1" for var in THREAD_VARS}
    jobs = []
    for spec in args.sets:
        masks, out = (LOGS / part for part in spec.split(":"))
        (out / "logs").mkdir(parents=True, exist_ok=True)
        for draw in sorted(int(p.stem[4:]) for p in masks.glob("draw*.csv")):
            for species in args.species:
                stem = f"{species.replace(' ', '_')}_draw{draw}"
                if all((out / f"{stem}_{arm}_fit.csv").exists() for arm in args.arms):
                    continue
                jobs.append((masks, out, draw, species, stem))
    print(f"{len(jobs)} jobs, {args.workers} at a time", flush=True)

    def run(job):
        masks, out, draw, species, stem = job
        command = ["nice", "-n", str(NICE), *RUN, "--arms", *args.arms, "--species", species]
        command += ["--draws", str(draw), "--masks", str(masks), "--out", str(out)]
        start = time.time()
        with open(out / "logs" / f"{stem}.log", "w") as log:
            code = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=log).returncode
        print(f"{out.name} {stem}: exit {code}, {time.time() - start:.0f}s", flush=True)
        return code

    with ThreadPoolExecutor(args.workers) as pool:
        codes = list(pool.map(run, jobs))
    failed = sum(code != 0 for code in codes)
    print(f"done: {len(jobs) - failed} ok, {failed} failed", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
