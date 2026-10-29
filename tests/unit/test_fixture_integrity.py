from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cto_order_agent.datasource.mock.adapter import load_dataset
from cto_order_agent.domain.errors import FixtureIntegrityError


@pytest.mark.unit
def test_all_scenarios_load_clean(dataclass_dir: Path) -> None:
    dataset = load_dataset(dataclass_dir)
    assert len(dataset.sales_orders) == 14
    assert len(dataset.production_orders) >= 15


@pytest.mark.unit
def test_orphan_production_order_fails_fast(tmp_path: Path, dataclass_dir: Path) -> None:
    for path in dataclass_dir.glob("*.json"):
        shutil.copy(path, tmp_path / path.name)

    target = tmp_path / "on-track.json"
    payload = json.loads(target.read_text())
    payload["productionOrders"][0]["sales_order_item"] = "999999"
    target.write_text(json.dumps(payload))

    with pytest.raises(FixtureIntegrityError, match="orphan sales order item"):
        load_dataset(tmp_path)


@pytest.mark.unit
def test_missing_synthetic_header_fails(tmp_path: Path, dataclass_dir: Path) -> None:
    for path in dataclass_dir.glob("*.json"):
        shutil.copy(path, tmp_path / path.name)

    target = tmp_path / "on-track.json"
    payload = json.loads(target.read_text())
    payload["_meta"]["synthetic"] = False
    target.write_text(json.dumps(payload))

    with pytest.raises(FixtureIntegrityError, match="synthetic"):
        load_dataset(tmp_path)


@pytest.mark.unit
def test_duplicate_sales_order_fails(tmp_path: Path, dataclass_dir: Path) -> None:
    for path in dataclass_dir.glob("*.json"):
        shutil.copy(path, tmp_path / path.name)

    source = json.loads((tmp_path / "on-track.json").read_text())
    (tmp_path / "duplicate.json").write_text(json.dumps(source))

    with pytest.raises(FixtureIntegrityError, match="duplicate sales order"):
        load_dataset(tmp_path)
