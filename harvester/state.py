from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from harvester.config import DATA_DIR
from harvester.models import HarvestState, TestState


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def load_harvest_state() -> HarvestState:
    path = DATA_DIR / "harvest_state.json"
    if path.exists():
        return HarvestState(**json.loads(path.read_text()))
    return HarvestState()


def save_harvest_state(state: HarvestState):
    _ensure_dir()
    state.last_updated = datetime.now(timezone.utc).isoformat()
    _atomic_write(DATA_DIR / "harvest_state.json", state.model_dump())


def load_test_state() -> TestState:
    path = DATA_DIR / "test_state.json"
    if path.exists():
        return TestState(**json.loads(path.read_text()))
    return TestState()


def save_test_state(state: TestState):
    _ensure_dir()
    state.last_updated = datetime.now(timezone.utc).isoformat()
    _atomic_write(DATA_DIR / "test_state.json", state.model_dump())


def save_streams(streams: list, filename: str = "harvested_streams.json"):
    _ensure_dir()
    path = DATA_DIR / filename
    _atomic_write(path, [s.model_dump() for s in streams])


def load_streams(filename: str = "harvested_streams.json") -> list[dict]:
    path = DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_results(results: list, filename: str = "test_results.json"):
    _ensure_dir()
    path = DATA_DIR / filename
    _atomic_write(path, [r.model_dump() for r in results])
