import json
import random

import pytest

from lcsw.content import CONTENT_AREAS, ContentError, load_flashcards, load_questions
from lcsw.progress import MAX_BOX, Progress
from lcsw.quiz import Quiz, allocate_by_weight, build_practice, build_weighted_exam


# ---- content ---------------------------------------------------------------

def test_bank_loads_and_covers_every_area():
    qs = load_questions()
    cards = load_flashcards()
    for area in CONTENT_AREAS:
        assert sum(q.area == area for q in qs) >= 10, area
        assert sum(c.area == area for c in cards) >= 10, area


def test_weights_sum_to_one():
    assert sum(a["weight"] for a in CONTENT_AREAS.values()) == pytest.approx(1.0)


def test_custom_bank_is_merged_and_validated(tmp_path):
    q = {"id": "x1", "area": "ETH", "topic": "t", "stem": "s", "options": ["a", "b"],
         "answer": 1, "explanation": "e"}
    (tmp_path / "questions.json").write_text(json.dumps([q]))
    (tmp_path / "questions_custom.json").write_text(json.dumps([{**q, "id": "x2"}]))
    assert [x.id for x in load_questions(tmp_path)] == ["x1", "x2"]

    (tmp_path / "questions_custom.json").write_text(json.dumps([q]))  # duplicate id
    with pytest.raises(ContentError):
        load_questions(tmp_path)

    (tmp_path / "questions_custom.json").write_text(json.dumps([{**q, "id": "x3", "answer": 5}]))
    with pytest.raises(ContentError):
        load_questions(tmp_path)


# ---- quiz ------------------------------------------------------------------

def test_allocation_follows_weights_and_caps():
    alloc = allocate_by_weight(100, {"HGD": 50, "ADT": 50, "PCI": 50, "ETH": 50})
    assert alloc == {"HGD": 24, "ADT": 30, "PCI": 27, "ETH": 19}
    # ADT only has 5: its shortfall gets redistributed, total still met
    alloc = allocate_by_weight(40, {"HGD": 50, "ADT": 5, "PCI": 50, "ETH": 50})
    assert alloc["ADT"] == 5 and sum(alloc.values()) == 40
    # can't exceed what exists
    assert sum(allocate_by_weight(999, {"HGD": 2, "ADT": 3, "PCI": 0, "ETH": 1}).values()) == 6


def test_weighted_exam_has_no_duplicates():
    qs = load_questions()
    exam = build_weighted_exam(qs, 40, random.Random(1))
    assert len(exam) == 40 and len({q.id for q in exam}) == 40


def test_quiz_scoring_survives_option_shuffle():
    qs = load_questions()[:5]
    quiz = Quiz.create("practice", qs, random.Random(7))
    for item in quiz.items:
        correct_pos = item.order.index(item.question.answer)
        assert item.display_options()[correct_pos] == item.question.correct_text
    # answer first two right, third wrong, leave the rest blank
    for i in range(3):
        quiz.index = i
        item = quiz.current
        right = item.order.index(item.question.answer)
        quiz.answer(right if i < 2 else (right + 1) % len(item.order))
    s = quiz.score()
    assert (s["correct"], s["answered"], s["total"]) == (2, 3, 5)


def test_practice_filters():
    qs = load_questions()
    only = build_practice(qs, ["ETH"], 100, random.Random(0))
    assert only and all(q.area == "ETH" for q in only)
    ids = {qs[0].id, qs[1].id}
    assert {q.id for q in build_practice(qs, None, 10, random.Random(0), only_ids=ids)} == ids


def test_timer():
    quiz = Quiz.create("exam", load_questions()[:2], random.Random(0), time_limit_s=60, started_at=100)
    assert quiz.remaining_s(130) == 30
    assert quiz.remaining_s(500) == 0


# ---- progress --------------------------------------------------------------

def test_progress_roundtrip_and_missed(tmp_path):
    path = tmp_path / "p.json"
    p = Progress(path)
    p.record_attempt("q1", "ETH", False, "practice")
    p.record_attempt("q2", "ADT", True, "practice")
    p.record_attempt("q1", "ETH", True, "review")
    p.record_attempt("q3", "ADT", False, "exam")
    p.save()

    p2 = Progress(path)
    assert p2.missed_ids() == {"q3"}
    stats = p2.area_stats()
    assert stats["ADT"]["pct"] == 50 and stats["ETH"]["total"] == 2


def test_corrupt_progress_file_is_preserved(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json")
    p = Progress(path)
    assert p.data["attempts"] == []
    assert (tmp_path / "p.corrupt.json").exists()


def test_leitner_boxes():
    p = Progress(None)
    for _ in range(10):
        p.grade_card("c", True)
    assert p.card_box("c") == MAX_BOX
    p.grade_card("c", False)
    assert p.card_box("c") == 1


def test_next_card_prefers_unknown_cards():
    p = Progress(None)
    for _ in range(5):
        p.grade_card("known", True)
    picks = [p.next_card(["known", "new"], random.Random(i)) for i in range(400)]
    assert picks.count("new") > picks.count("known") * 5


def test_load_dict_rejects_garbage():
    with pytest.raises(ValueError):
        Progress(None).load_dict({"hello": 1})


def test_longest_option_is_not_a_giveaway():
    """'Always pick the longest answer' shouldn't beat chance by much."""
    qs = load_questions()
    hits = sum(max(range(len(q.options)), key=lambda i: len(q.options[i])) == q.answer for q in qs)
    chance = sum(1 / len(q.options) for q in qs)
    assert hits <= chance * 1.4, f"longest option is correct {hits}/{len(qs)} times"
