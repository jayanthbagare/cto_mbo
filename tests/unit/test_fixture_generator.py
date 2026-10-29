from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

GENERATOR = Path(__file__).resolve().parents[2] / "fixtures" / "generate.py"


def _load():
    spec = importlib.util.spec_from_file_location("fixture_generator", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_generator_is_deterministic(tmp_path: Path) -> None:
    generator = _load()
    assert generator.main(["--out", str(tmp_path)]) == 0
    first = {p.name: p.read_text() for p in tmp_path.glob("*.json")}
    assert generator.main(["--out", str(tmp_path)]) == 0
    second = {p.name: p.read_text() for p in tmp_path.glob("*.json")}
    assert first == second
    assert len([name for name in first if not name.endswith(".expected.json")]) == 12


@pytest.mark.unit
def test_check_fails_on_mutated_fixture(tmp_path: Path) -> None:
    generator = _load()
    assert generator.main(["--out", str(tmp_path)]) == 0
    assert generator.main(["--check", "--out", str(tmp_path)]) == 0

    target = tmp_path / "on-track.json"
    payload = json.loads(target.read_text())
    payload["salesOrders"][0]["requested_delivery_date"] = "2030-01-01"
    target.write_text(json.dumps(payload))
    assert generator.main(["--check", "--out", str(tmp_path)]) == 1


@pytest.mark.unit
def test_every_fixture_declares_synthetic_header(tmp_path: Path) -> None:
    generator = _load()
    generator.main(["--out", str(tmp_path)])
    for path in tmp_path.glob("*.json"):
        if path.name.endswith(".expected.json"):
            continue
        meta = json.loads(path.read_text())["_meta"]
        assert meta["synthetic"] is True
        assert "SYNTHETIC DATA" in meta["notice"]
        assert meta["seed"] == 42


@pytest.mark.unit
def test_rejects_unsupported_seed(tmp_path: Path) -> None:
    assert _load().main(["--seed", "7", "--out", str(tmp_path)]) == 2
