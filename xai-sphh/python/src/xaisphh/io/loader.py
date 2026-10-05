"""
Trace file loading and schema validation.

Provides functions to load one or many CSV trace files into a single
:class:`pandas.DataFrame` and validate the result against the schema defined in
:mod:`xaisphh.io.schema`. Also provides manifest loading utilities that extract
per-run metadata (technique name, domain, stub flag) from the JSON sidecar files
written by the Java experiment runner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from xaisphh.io.schema import FIXED_COLUMNS, FIXED_DTYPES


def load_trace(path: Path) -> pd.DataFrame:
    """Load a single CSV trace file and validate its schema.

    Reads the file, checks that all fixed columns are present, casts them to
    the declared dtypes, and returns the dataframe with dynamic columns
    (``feat_*`` and ``score_*``) appended after the fixed ones.

    The ``log_return`` column may contain empty CSV fields (written by
    ``CsvTraceWriter`` for non-positive objectives per DD-08); these are
    loaded as ``NaN`` by pandas automatically.

    :param path: path to the CSV trace file produced by ``CsvTraceWriter``
    :return: validated dataframe with one row per iteration
    :raises FileNotFoundError: if *path* does not exist
    :raises ValueError: if required columns are missing or dtypes cannot be cast
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    df = pd.read_csv(path, dtype=str)  # load everything as str first for safe casting

    # Validate that all fixed columns are present.
    validate_schema(df)

    # Cast fixed columns to their declared dtypes.
    for col, dtype in FIXED_DTYPES.items():
        if dtype == "bool":
            # CSV stores True/False as strings; convert case-insensitively.
            df[col] = df[col].str.strip().str.lower().map(
                {"true": True, "false": False, "1": True, "0": False}
            ).astype("boolean")
        elif dtype in ("float64",):
            # Empty fields (e.g. log_return for non-positive objectives) become NaN.
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        elif dtype == "int64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("int64")
        elif dtype == "int32":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("int32")
        elif dtype == "string":
            df[col] = df[col].astype("string")

    # Cast dynamic feature and score columns to float64.
    dynamic_cols = [c for c in df.columns if c not in FIXED_COLUMNS]
    for col in dynamic_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # Reorder: fixed columns first, then dynamic columns in their original order.
    ordered = FIXED_COLUMNS + [c for c in df.columns if c not in FIXED_COLUMNS]
    return df[ordered]


def load_manifest(path: Path) -> dict:
    """Load a single JSON run manifest produced by the Java experiment runner.

    :param path: path to the manifest JSON file
    :return: parsed manifest as a plain dictionary
    :raises FileNotFoundError: if *path* does not exist
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_manifests(directory: Path, pattern: str = "manifest_*.json") -> dict[str, dict]:
    """Load all run manifests from *directory* and return them keyed by run ID.

    Each manifest file is matched by *pattern* and loaded via :func:`load_manifest`.
    The key of the returned dictionary is the ``runId`` field from the manifest
    (typically the filename stem, e.g. ``SP-CF-LA_SAT_0_42``).

    :param directory: directory containing manifest JSON files
    :param pattern: glob pattern used to find manifest files
    :return: mapping from run ID to manifest dict; empty if no manifests found
    :raises FileNotFoundError: if *directory* does not exist
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Trace directory not found: {directory}")

    result: dict[str, dict] = {}
    for path in sorted(directory.glob(pattern)):
        manifest = load_manifest(path)
        run_id = manifest.get("runId", path.stem.removeprefix("manifest_"))
        result[run_id] = manifest
    return result


def load_manifests_for_traces(directory: Path) -> dict[str, dict]:
    """Match manifests to trace-file UUID run IDs by pairing filenames with the same stem.

    Trace files are named ``trace_{stem}.csv`` and manifests are named
    ``manifest_{stem}.json``. The ``run_id`` column in the trace CSV is a UUID
    that differs from the manifest's ``runId`` (which is the stem). This function
    reads the first row of each trace CSV to obtain the UUID, then maps it to
    the manifest with the matching stem.

    :param directory: directory containing both trace CSVs and manifest JSON files
    :return: mapping from trace-row UUID to manifest dict
    :raises FileNotFoundError: if *directory* does not exist
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Trace directory not found: {directory}")

    result: dict[str, dict] = {}
    for csv_path in sorted(directory.glob("trace_*.csv")):
        stem = csv_path.name.removeprefix("trace_").removesuffix(".csv")
        manifest_path = directory / f"manifest_{stem}.json"
        if not manifest_path.exists():
            continue
        try:
            # Read only the first row to cheaply obtain the UUID run_id.
            sample = pd.read_csv(csv_path, nrows=1, usecols=["run_id"])
            if not sample.empty:
                uuid = str(sample["run_id"].iloc[0])
                result[uuid] = load_manifest(manifest_path)
        except Exception:
            pass
    return result


def technique_from_run_id(run_id: str) -> str:
    """Extract the technique name from a run ID.

    Run IDs follow the format ``TECHNIQUE_DOMAIN_INSTANCE_SEED``, where
    TECHNIQUE uses hyphens internally (e.g. ``SP-CF-LA``) and the fields are
    separated by underscores. The technique name is the first underscore-delimited
    component.

    :param run_id: run identifier string
    :return: technique name component
    """
    return run_id.split("_")[0]


def build_run_metadata(
    df: pd.DataFrame,
    manifests: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Build a per-row metadata frame aligned with *df*.

    Adds ``technique``, ``domain``, ``stub`` columns. When *manifests* is
    provided, values are read from the manifest records. Otherwise, technique
    and domain are derived by parsing ``run_id``, and ``stub`` defaults to True
    (conservative assumption when no manifest is available).

    :param df: trace dataframe with a ``run_id`` column
    :param manifests: optional mapping from run ID to manifest dict
    :return: dataframe with columns ``run_id``, ``technique``, ``domain``,
             ``instance``, ``seed``, ``stub``
    """
    meta_rows = []
    for run_id in df["run_id"].unique():
        if manifests and run_id in manifests:
            m = manifests[run_id]
            cfg = m.get("config", {})
            technique = cfg.get("techniqueName", technique_from_run_id(run_id))
            domain    = cfg.get("domain", "unknown")
            instance  = int(cfg.get("instanceIndex", -1))
            seed      = int(cfg.get("seed", -1))
            stub      = bool(m.get("stub", True))
        else:
            parts    = run_id.split("_")
            technique = parts[0] if len(parts) >= 1 else run_id
            domain    = parts[1] if len(parts) >= 2 else "unknown"
            instance  = int(parts[2]) if len(parts) >= 3 else -1
            seed      = int(parts[3]) if len(parts) >= 4 else -1
            stub      = True  # conservative default
        meta_rows.append({
            "run_id":    run_id,
            "technique": technique,
            "domain":    domain,
            "instance":  instance,
            "seed":      seed,
            "stub":      stub,
        })
    return pd.DataFrame(meta_rows)


def load_traces(directory: Path, pattern: str = "*.csv") -> pd.DataFrame:
    """Load all trace files matching *pattern* from *directory* and concatenate them.

    Each file is loaded via :func:`load_trace`. The resulting dataframes are
    concatenated along the row axis with the index reset.

    :param directory: directory containing CSV trace files
    :param pattern: glob pattern used to find trace files within *directory*
    :return: concatenated dataframe of all traces
    :raises FileNotFoundError: if *directory* does not exist
    :raises ValueError: if no matching files are found
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Trace directory not found: {directory}")

    files = sorted(directory.glob(pattern))
    if not files:
        raise ValueError(
            f"No files matching '{pattern}' found in {directory}."
        )

    frames = [load_trace(f) for f in files]
    return pd.concat(frames, ignore_index=True)


def validate_schema(df: pd.DataFrame) -> None:
    """Assert that *df* contains all required fixed columns.

    :param df: dataframe to validate
    :raises ValueError: if any fixed column is absent
    """
    missing = [col for col in FIXED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Trace dataframe is missing required fixed columns: {missing}. "
            f"Present columns: {list(df.columns)}"
        )
