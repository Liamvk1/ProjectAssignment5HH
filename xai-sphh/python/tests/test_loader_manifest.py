"""
Tests for manifest loading and run metadata utilities in xaisphh.io.loader.

Item 1 (manifest loading) and Item 8 (stub flag).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from xaisphh.io.loader import (
    load_manifest,
    load_manifests,
    technique_from_run_id,
    build_run_metadata,
)


# ---------------------------------------------------------------------------
# technique_from_run_id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("run_id,expected", [
    ("SP-CF-LA_SAT_0_42",     "SP-CF-LA"),
    ("MP-CF_SAT_0_42",        "MP-CF"),
    ("SP-CF-AILTA_SAT_0_42",  "SP-CF-AILTA"),
    ("SP-SR-LA_BinPacking_3_123", "SP-SR-LA"),
])
def test_technique_from_run_id(run_id: str, expected: str) -> None:
    """technique_from_run_id must return the technique component of the run ID."""
    assert technique_from_run_id(run_id) == expected


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------

def test_load_manifest_parses_json() -> None:
    """load_manifest must return the parsed JSON as a dict."""
    manifest = {
        "runId": "SP-CF-LA_SAT_0_42",
        "config": {"techniqueName": "SP-CF-LA", "domain": "SAT"},
        "stub": True,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(manifest, fh)
        path = Path(fh.name)

    result = load_manifest(path)
    assert result["runId"] == "SP-CF-LA_SAT_0_42"
    assert result["config"]["techniqueName"] == "SP-CF-LA"
    assert result["stub"] is True


def test_load_manifest_raises_on_missing_file() -> None:
    """load_manifest must raise FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError):
        load_manifest(Path("/nonexistent/path.json"))


# ---------------------------------------------------------------------------
# load_manifests
# ---------------------------------------------------------------------------

def test_load_manifests_returns_keyed_by_run_id() -> None:
    """load_manifests must return a dict keyed by runId."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        for name in ["SP-CF-LA_SAT_0_42", "MP-CF_SAT_0_42"]:
            m = {"runId": name, "config": {"techniqueName": name.split("_")[0]}, "stub": True}
            (tmpdir / f"manifest_{name}.json").write_text(json.dumps(m))

        result = load_manifests(tmpdir)
        assert set(result.keys()) == {"SP-CF-LA_SAT_0_42", "MP-CF_SAT_0_42"}


def test_load_manifests_empty_directory_returns_empty_dict() -> None:
    """load_manifests must return an empty dict when no manifests are found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = load_manifests(Path(tmpdir))
        assert result == {}


# ---------------------------------------------------------------------------
# build_run_metadata
# ---------------------------------------------------------------------------

def test_build_run_metadata_from_manifests() -> None:
    """build_run_metadata must extract technique from manifest config."""
    df = pd.DataFrame({"run_id": ["SP-CF-LA_SAT_0_42", "MP-CF_SAT_0_42"]})
    manifests = {
        "SP-CF-LA_SAT_0_42": {
            "runId": "SP-CF-LA_SAT_0_42",
            "config": {"techniqueName": "SP-CF-LA", "domain": "SAT",
                       "instanceIndex": 0, "seed": 42},
            "stub": True,
        },
        "MP-CF_SAT_0_42": {
            "runId": "MP-CF_SAT_0_42",
            "config": {"techniqueName": "MP-CF", "domain": "SAT",
                       "instanceIndex": 0, "seed": 42},
            "stub": True,
        },
    }

    meta = build_run_metadata(df, manifests)
    assert set(meta["technique"]) == {"SP-CF-LA", "MP-CF"}
    assert all(meta["domain"] == "SAT")
    assert all(meta["stub"] == True)


def test_build_run_metadata_falls_back_to_run_id_parsing() -> None:
    """build_run_metadata must parse technique from run_id when no manifests are given."""
    df = pd.DataFrame({"run_id": ["SP-CF-LA_SAT_0_42"]})
    meta = build_run_metadata(df, manifests=None)
    assert meta.loc[0, "technique"] == "SP-CF-LA"
    assert meta.loc[0, "domain"]    == "SAT"
    assert meta.loc[0, "stub"]      == True  # conservative default
