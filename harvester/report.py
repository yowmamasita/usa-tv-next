from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from harvester.config import DATA_DIR
from harvester.models import Report, StreamTestResult


def generate_report(results: list[StreamTestResult], sources_total: int = 0) -> Report:
    working = [r for r in results if r.status == "working"]
    dead = [r for r in results if r.status == "dead"]
    timeout = [r for r in results if r.status == "timeout"]

    return Report(
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary={
            "total_sources": sources_total,
            "total_streams_tested": len(results),
            "working": len(working),
            "dead": len(dead),
            "timeout": len(timeout),
            "working_pct": round(len(working) / max(len(results), 1) * 100, 1),
        },
        streams=sorted(results, key=lambda r: (r.status != "working", -r.response_time_ms)),
    )


def save_report(report: Report, filename: str = "report.json"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    path.write_text(json.dumps(report.model_dump(), indent=2))


def print_summary(report: Report):
    s = report.summary
    print(f"\n{'='*50}")
    print(f"  IPTV Stream Harvester Report")
    print(f"  Generated: {report.generated_at}")
    print(f"{'='*50}")
    print(f"  Total streams tested: {s.get('total_streams_tested', 0):,}")
    print(f"  Working:  {s.get('working', 0):,} ({s.get('working_pct', 0)}%)")
    print(f"  Dead:     {s.get('dead', 0):,}")
    print(f"  Timeout:  {s.get('timeout', 0):,}")
    print(f"{'='*50}\n")
