"""
Parallel experiment runner with resume support.

Executes all YAML configs in a directory using the Java Gradle runner, in
parallel, skipping any run whose trace CSV and manifest JSON already exist.
Stops on the first fatal error per run but allows other runs to continue.

Item 7.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def run_single_config(config_path: Path, repo_root: Path, dry_run: bool) -> tuple[str, bool, str]:
    """Execute a single YAML config via Gradle.

    :param config_path: path to the YAML experiment config
    :param repo_root: repository root containing build.gradle
    :param dry_run: if True, print the command but do not execute
    :return: tuple of (config name, success, message)
    """
    name = config_path.stem

    # Check if output already exists (resume support): derive expected paths from
    # the config stem (format: TECHNIQUE_DOMAIN_INSTANCE_SEED).
    import yaml as _yaml  # type: ignore[import-untyped]
    try:
        with config_path.open(encoding="utf-8") as fh:
            cfg = _yaml.safe_load(fh)
        out_dir = Path(cfg.get("outputDirectory", "data/raw/traces"))
        if not out_dir.is_absolute():
            out_dir = repo_root / out_dir
        trace_path    = out_dir / f"trace_{name}.csv"
        manifest_path = out_dir / f"manifest_{name}.json"
        if trace_path.exists() and manifest_path.exists():
            return name, True, f"SKIP (already exists): {name}"
    except Exception as exc:
        return name, False, f"ERROR reading config {name}: {exc}"

    cmd = [
        str(repo_root / "gradlew"),
        "run",
        f"--args=--config {config_path}",
    ]

    if dry_run:
        return name, True, f"DRY-RUN: {' '.join(cmd)}"

    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True, timeout=1800
        )
        if result.returncode == 0:
            return name, True, f"OK: {name}"
        return name, False, (
            f"FAIL [{result.returncode}]: {name}\n"
            f"  stdout: {result.stdout[-500:]}\n"
            f"  stderr: {result.stderr[-500:]}"
        )
    except subprocess.TimeoutExpired:
        return name, False, f"TIMEOUT: {name}"
    except Exception as exc:
        return name, False, f"ERROR running {name}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all YAML experiment configs in a directory, in parallel, with resume."
    )
    parser.add_argument(
        "--configs", type=Path, required=True,
        help="Directory containing YAML config files to execute."
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path("."),
        help="Repository root directory containing gradlew (default: current directory)."
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of parallel workers (default: 4)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print commands without executing them."
    )
    args = parser.parse_args()

    config_files = sorted(args.configs.glob("*.yaml"))
    if not config_files:
        print(f"No YAML files found in {args.configs}.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(config_files)} configs. Running with {args.workers} workers.")

    n_ok = n_fail = n_skip = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_single_config, cfg, args.repo_root.resolve(), args.dry_run): cfg
            for cfg in config_files
        }
        for future in as_completed(futures):
            name, ok, msg = future.result()
            print(msg)
            if "SKIP" in msg:
                n_skip += 1
            elif ok:
                n_ok += 1
            else:
                n_fail += 1

    print(f"\nDone. OK={n_ok}, SKIP={n_skip}, FAIL={n_fail}.")
    if n_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
