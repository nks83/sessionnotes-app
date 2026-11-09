"""Persistent study progress: question attempts and flashcard (Leitner) boxes."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

_USE_DEFAULT = object()


def default_path() -> Path:
    return Path(os.environ.get("LCSW_PROGRESS_PATH", "progress.json"))


MAX_BOX = 5
SCHEMA_VERSION = 1


def _empty() -> dict:
    return {"version": SCHEMA_VERSION, "attempts": [], "cards": {}, "exams": []}


class Progress:
    def __init__(self, path=_USE_DEFAULT):
        """path=None keeps progress in memory only (used by tests)."""
        if path is _USE_DEFAULT:
            path = default_path()
        self.path = Path(path) if path else None
        self.data = _empty()
        if self.path and self.path.exists():
            try:
                self.load_dict(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError):
                # Don't destroy a corrupt file; park it and start fresh.
                self.path.rename(self.path.with_suffix(".corrupt.json"))

    # ---- persistence -------------------------------------------------
    def load_dict(self, data: dict) -> None:
        if not isinstance(data, dict) or "attempts" not in data:
            raise ValueError("Not a progress file")
        merged = _empty()
        merged.update({k: data[k] for k in ("attempts", "cards", "exams") if k in data})
        self.data = merged

    def save(self) -> None:
        if not self.path:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def to_json(self) -> str:
        return json.dumps(self.data, indent=1)

    def reset(self) -> None:
        self.data = _empty()
        self.save()

    # ---- questions ---------------------------------------------------
    def record_attempt(self, qid: str, area: str, correct: bool, mode: str) -> None:
        self.data["attempts"].append(
            {"qid": qid, "area": area, "correct": bool(correct), "mode": mode, "ts": time.time()}
        )

    def record_exam(self, score: dict) -> None:
        self.data["exams"].append({"ts": time.time(), **score})

    def latest_by_question(self) -> dict[str, bool]:
        latest: dict[str, bool] = {}
        for a in self.data["attempts"]:
            latest[a["qid"]] = a["correct"]
        return latest

    def missed_ids(self) -> set[str]:
        """Questions whose most recent attempt was wrong."""
        return {qid for qid, ok in self.latest_by_question().items() if not ok}

    def seen_ids(self) -> set[str]:
        return {a["qid"] for a in self.data["attempts"]}

    def area_stats(self) -> dict[str, dict[str, float]]:
        stats: dict[str, dict[str, float]] = {}
        for a in self.data["attempts"]:
            s = stats.setdefault(a["area"], {"correct": 0, "total": 0})
            s["total"] += 1
            s["correct"] += int(a["correct"])
        for s in stats.values():
            s["pct"] = s["correct"] / s["total"] * 100 if s["total"] else 0.0
        return stats

    # ---- flashcards (Leitner system) -----------------------------------
    def card_box(self, cid: str) -> int:
        return self.data["cards"].get(cid, 1)

    def grade_card(self, cid: str, knew_it: bool) -> int:
        box = min(self.card_box(cid) + 1, MAX_BOX) if knew_it else 1
        self.data["cards"][cid] = box
        return box

    def next_card(self, card_ids: list[str], rng: random.Random, exclude: str | None = None) -> str | None:
        """Pick a card, weighting lower boxes (less well known) much more heavily."""
        pool = [c for c in card_ids if c != exclude] or card_ids
        if not pool:
            return None
        weights = [2 ** (MAX_BOX - self.card_box(c)) for c in pool]
        return rng.choices(pool, weights=weights, k=1)[0]
