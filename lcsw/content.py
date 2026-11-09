"""Loading and validating study content (questions and flashcards)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ASWB Clinical exam content outline. Weights are the published share of
# scored questions per area.
CONTENT_AREAS: dict[str, dict] = {
    "HGD": {
        "name": "Human Growth & Development, Diversity, and Behavior in the Environment",
        "short": "Human Development & Diversity",
        "weight": 0.24,
    },
    "ADT": {
        "name": "Assessment, Diagnosis, and Treatment Planning",
        "short": "Assessment & Diagnosis",
        "weight": 0.30,
    },
    "PCI": {
        "name": "Psychotherapy, Clinical Interventions, and Case Management",
        "short": "Interventions & Case Mgmt",
        "weight": 0.27,
    },
    "ETH": {
        "name": "Professional Values and Ethics",
        "short": "Values & Ethics",
        "weight": 0.19,
    },
}

# Real exam: 170 questions (150 scored) in 4 hours.
EXAM_QUESTIONS = 170
EXAM_MINUTES = 240
MINUTES_PER_QUESTION = EXAM_MINUTES / EXAM_QUESTIONS


@dataclass(frozen=True)
class Question:
    id: str
    area: str
    topic: str
    stem: str
    options: tuple[str, ...]
    answer: int  # index into options
    explanation: str
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def correct_text(self) -> str:
        return self.options[self.answer]


@dataclass(frozen=True)
class Flashcard:
    id: str
    area: str
    term: str
    definition: str


class ContentError(ValueError):
    pass


def _parse_question(raw: dict) -> Question:
    required = ("id", "area", "topic", "stem", "options", "answer", "explanation")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ContentError(f"Question {raw.get('id', '?')} missing fields: {missing}")
    q = Question(
        id=str(raw["id"]),
        area=raw["area"],
        topic=raw["topic"],
        stem=raw["stem"].strip(),
        options=tuple(o.strip() for o in raw["options"]),
        answer=int(raw["answer"]),
        explanation=raw["explanation"].strip(),
        tags=tuple(raw.get("tags", ())),
    )
    if q.area not in CONTENT_AREAS:
        raise ContentError(f"Question {q.id}: unknown area {q.area!r}")
    if len(q.options) < 2:
        raise ContentError(f"Question {q.id}: needs at least 2 options")
    if len(set(q.options)) != len(q.options):
        raise ContentError(f"Question {q.id}: duplicate options")
    if not 0 <= q.answer < len(q.options):
        raise ContentError(f"Question {q.id}: answer index out of range")
    return q


def _parse_flashcard(raw: dict) -> Flashcard:
    for k in ("id", "area", "term", "definition"):
        if k not in raw:
            raise ContentError(f"Flashcard {raw.get('id', '?')} missing {k!r}")
    card = Flashcard(
        id=str(raw["id"]),
        area=raw["area"],
        term=raw["term"].strip(),
        definition=raw["definition"].strip(),
    )
    if card.area not in CONTENT_AREAS:
        raise ContentError(f"Flashcard {card.id}: unknown area {card.area!r}")
    return card


def _check_unique(items, kind: str) -> None:
    seen: set[str] = set()
    for it in items:
        if it.id in seen:
            raise ContentError(f"Duplicate {kind} id: {it.id}")
        seen.add(it.id)


def _load_json_files(pattern: str, data_dir: Path) -> list[dict]:
    """Load every JSON file matching pattern (e.g. questions*.json) so users can
    drop in extra banks like questions_custom.json without editing the core file."""
    items: list[dict] = []
    for path in sorted(data_dir.glob(pattern)):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ContentError(f"{path.name}: top level must be a JSON list")
        items.extend(data)
    return items


def load_questions(data_dir: Path = DATA_DIR) -> list[Question]:
    qs = [_parse_question(r) for r in _load_json_files("questions*.json", data_dir)]
    _check_unique(qs, "question")
    return qs


def load_flashcards(data_dir: Path = DATA_DIR) -> list[Flashcard]:
    cards = [_parse_flashcard(r) for r in _load_json_files("flashcards*.json", data_dir)]
    _check_unique(cards, "flashcard")
    return cards
