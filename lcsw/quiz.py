"""Quiz construction and scoring (pure logic, no Streamlit)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .content import CONTENT_AREAS, Question


def allocate_by_weight(total: int, available: dict[str, int]) -> dict[str, int]:
    """Split `total` questions across areas proportional to ASWB weights,
    capped by how many questions each area actually has. Uses largest-remainder
    rounding, then redistributes any shortfall to areas with spare questions."""
    total = min(total, sum(available.values()))
    weights = {a: CONTENT_AREAS[a]["weight"] for a in available if available[a] > 0}
    if not weights or total <= 0:
        return {a: 0 for a in available}
    wsum = sum(weights.values())
    raw = {a: total * w / wsum for a, w in weights.items()}
    alloc = {a: min(math.floor(v), available[a]) for a, v in raw.items()}
    # Hand out the remainder, biggest fractional part first, then anywhere with room.
    order = sorted(weights, key=lambda a: raw[a] - math.floor(raw[a]), reverse=True)
    while sum(alloc.values()) < total:
        progressed = False
        for a in order:
            if sum(alloc.values()) >= total:
                break
            if alloc[a] < available[a]:
                alloc[a] += 1
                progressed = True
        if not progressed:
            break
    return {a: alloc.get(a, 0) for a in available}


def build_weighted_exam(questions: list[Question], total: int, rng: random.Random) -> list[Question]:
    by_area: dict[str, list[Question]] = {a: [] for a in CONTENT_AREAS}
    for q in questions:
        by_area[q.area].append(q)
    alloc = allocate_by_weight(total, {a: len(v) for a, v in by_area.items()})
    picked: list[Question] = []
    for area, n in alloc.items():
        picked.extend(rng.sample(by_area[area], n))
    rng.shuffle(picked)
    return picked


def build_practice(
    questions: list[Question],
    areas: list[str] | None,
    count: int,
    rng: random.Random,
    only_ids: set[str] | None = None,
) -> list[Question]:
    pool = [
        q
        for q in questions
        if (not areas or q.area in areas) and (only_ids is None or q.id in only_ids)
    ]
    return rng.sample(pool, min(count, len(pool)))


@dataclass
class QuizItem:
    question: Question
    order: list[int]  # display position -> original option index
    chosen: int | None = None  # original option index the user picked

    @property
    def answered(self) -> bool:
        return self.chosen is not None

    @property
    def correct(self) -> bool:
        return self.chosen == self.question.answer

    def display_options(self) -> list[str]:
        return [self.question.options[i] for i in self.order]


@dataclass
class Quiz:
    mode: str  # "practice" | "exam" | "review"
    items: list[QuizItem]
    time_limit_s: float | None = None
    started_at: float = 0.0
    finished: bool = False
    index: int = 0
    recorded: set[str] = field(default_factory=set)

    @classmethod
    def create(cls, mode, questions, rng, time_limit_s=None, started_at=0.0):
        items = []
        for q in questions:
            order = list(range(len(q.options)))
            rng.shuffle(order)
            items.append(QuizItem(q, order))
        return cls(mode=mode, items=items, time_limit_s=time_limit_s, started_at=started_at)

    @property
    def current(self) -> QuizItem:
        return self.items[self.index]

    def answer(self, display_pos: int) -> QuizItem:
        item = self.current
        item.chosen = item.order[display_pos]
        return item

    def remaining_s(self, now: float) -> float | None:
        if self.time_limit_s is None:
            return None
        return max(0.0, self.time_limit_s - (now - self.started_at))

    def score(self) -> dict:
        answered = [i for i in self.items if i.answered]
        correct = sum(i.correct for i in answered)
        by_area: dict[str, dict[str, int]] = {}
        for i in self.items:
            s = by_area.setdefault(i.question.area, {"correct": 0, "total": 0})
            s["total"] += 1
            s["correct"] += int(i.answered and i.correct)
        return {
            "total": len(self.items),
            "answered": len(answered),
            "correct": correct,
            "pct": (correct / len(self.items) * 100) if self.items else 0.0,
            "by_area": by_area,
        }
