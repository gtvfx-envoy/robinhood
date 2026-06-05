"""Decision journaling for agentic bot runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .risk import RiskResult
from .strategy import Decision, QuoteSnapshot


@dataclass(frozen=True)
class JournalEntry:
    timestamp: str
    dry_run: bool
    quote: dict[str, Any]
    decision: dict[str, Any]
    risk: dict[str, Any]


class DecisionJournal:
    """Append one JSON object per decision for later audit and backtesting."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def append(
        self,
        quote: QuoteSnapshot,
        decision: Decision,
        risk: RiskResult,
        dry_run: bool,
    ) -> JournalEntry:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = JournalEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            dry_run=dry_run,
            quote=asdict(quote),
            decision=asdict(decision),
            risk=asdict(risk),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_json_safe(asdict(entry)), sort_keys=True))
            handle.write("\n")
        return entry


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
