"""LCSW Study Buddy: practice for the ASWB Clinical exam."""

from __future__ import annotations

import json
import random
import time

import streamlit as st

from lcsw.content import (
    CONTENT_AREAS,
    EXAM_MINUTES,
    EXAM_QUESTIONS,
    MINUTES_PER_QUESTION,
    load_flashcards,
    load_questions,
)
from lcsw.progress import MAX_BOX, Progress
from lcsw.quiz import Quiz, build_practice, build_weighted_exam

st.set_page_config(page_title="LCSW Study Buddy", page_icon="📚", layout="centered")

TARGET_PCT = 70  # rough target; ASWB's real cut score varies by exam form


@st.cache_data
def get_questions():
    return load_questions()


@st.cache_data
def get_flashcards():
    return load_flashcards()


QUESTIONS = get_questions()
Q_BY_ID = {q.id: q for q in QUESTIONS}
CARDS = get_flashcards()
CARD_BY_ID = {c.id: c for c in CARDS}


def progress() -> Progress:
    if "progress" not in st.session_state:
        st.session_state.progress = Progress()
    return st.session_state.progress


def rng() -> random.Random:
    if "rng" not in st.session_state:
        st.session_state.rng = random.Random()
    return st.session_state.rng


def area_label(code: str) -> str:
    return CONTENT_AREAS[code]["short"]


def fmt_secs(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


# ---------------------------------------------------------------------------
# Quiz engine UI (shared by Practice, Mock Exam, and Review Missed)
# ---------------------------------------------------------------------------

def quiz_key(name: str) -> str:
    return f"quiz_{name}"


def finish_quiz(quiz: Quiz, record_exam: bool = True) -> None:
    if quiz.finished:
        return
    quiz.finished = True
    p = progress()
    for item in quiz.items:
        if item.answered and item.question.id not in quiz.recorded:
            p.record_attempt(item.question.id, item.question.area, item.correct, quiz.mode)
            quiz.recorded.add(item.question.id)
    if quiz.mode == "exam" and record_exam:
        s = quiz.score()
        p.record_exam({k: s[k] for k in ("total", "answered", "correct", "pct", "by_area")})
    p.save()


def render_results(quiz: Quiz, name: str) -> None:
    s = quiz.score()
    st.subheader("Results")
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{s['pct']:.0f}%")
    c2.metric("Correct", f"{s['correct']} / {s['total']}")
    c3.metric("Unanswered", s["total"] - s["answered"])
    if quiz.mode == "exam":
        if s["pct"] >= TARGET_PCT:
            st.success(f"At or above the ~{TARGET_PCT}% target. Keep it up.")
        else:
            st.warning(f"Below the ~{TARGET_PCT}% target. Check the areas below and drill your weakest one.")

    st.markdown("**By content area**")
    for area, a in sorted(s["by_area"].items()):
        pct = a["correct"] / a["total"] if a["total"] else 0
        st.progress(pct, text=f"{area_label(area)}: {a['correct']}/{a['total']} ({pct:.0%})")

    st.markdown("**Question review**")
    show_all = st.toggle("Show correct answers too", value=False, key=f"{name}_showall")
    for n, item in enumerate(quiz.items, 1):
        if item.correct and not show_all:
            continue
        icon = "✅" if item.correct else ("⬜" if not item.answered else "❌")
        with st.expander(f"{icon} Q{n} · {item.question.topic}"):
            st.write(item.question.stem)
            if item.answered and not item.correct:
                st.markdown(f"**Your answer:** {item.question.options[item.chosen]}")
            st.markdown(f"**Correct answer:** {item.question.correct_text}")
            st.info(item.question.explanation)

    if st.button("Start a new set", type="primary", key=f"{name}_new"):
        del st.session_state[quiz_key(name)]
        st.rerun()


def render_quiz(name: str) -> None:
    quiz: Quiz = st.session_state[quiz_key(name)]
    if quiz.finished:
        render_results(quiz, name)
        return

    remaining = quiz.remaining_s(time.time())
    if remaining is not None and remaining <= 0:
        finish_quiz(quiz)
        st.warning("Time's up! Your exam was submitted automatically.")
        render_results(quiz, name)
        return

    item = quiz.current
    q = item.question
    n_answered = sum(i.answered for i in quiz.items)

    top = st.columns([3, 2])
    top[0].caption(f"Question {quiz.index + 1} of {len(quiz.items)} · {area_label(q.area)} · {q.topic}")
    if remaining is not None:
        top[1].caption(f"⏱ Time left: **{fmt_secs(remaining)}** (updates when you click)")
    st.progress(n_answered / len(quiz.items))

    st.markdown(f"#### {q.stem}")
    options = item.display_options()
    instant_feedback = quiz.mode in ("practice", "review")
    locked = instant_feedback and item.answered

    current_pos = item.order.index(item.chosen) if item.answered else None
    radio_key = f"{name}_radio_{id(quiz)}_{quiz.index}"

    def on_pick():
        pos = st.session_state[radio_key]
        if pos is not None and not instant_feedback:
            quiz.answer(pos)

    choice = st.radio(
        "Choose one:",
        range(len(options)),
        format_func=lambda i: f"{'ABCD'[i] if i < 4 else i + 1}. {options[i]}",
        index=current_pos,
        key=radio_key,
        disabled=locked,
        on_change=on_pick,
        label_visibility="collapsed",
    )

    if instant_feedback:
        if not item.answered:
            if st.button("Submit answer", type="primary", disabled=choice is None, key=f"{name}_submit"):
                quiz.answer(choice)
                p = progress()
                p.record_attempt(q.id, q.area, item.correct, quiz.mode)
                quiz.recorded.add(q.id)
                p.save()
                st.rerun()
        else:
            if item.correct:
                st.success("Correct!")
            else:
                st.error(f"Not quite. Correct answer: **{q.correct_text}**")
            st.info(q.explanation)
            last = quiz.index == len(quiz.items) - 1
            if st.button("See results" if last else "Next question →", type="primary", key=f"{name}_next"):
                if last:
                    finish_quiz(quiz)
                else:
                    quiz.index += 1
                st.rerun()
    else:
        nav = st.columns(3)
        if nav[0].button("← Previous", disabled=quiz.index == 0, key=f"{name}_prev"):
            quiz.index -= 1
            st.rerun()
        if nav[1].button("Next →", disabled=quiz.index == len(quiz.items) - 1, key=f"{name}_nextx"):
            quiz.index += 1
            st.rerun()
        if nav[2].button("Finish exam", type="primary", key=f"{name}_finish"):
            st.session_state[f"{name}_confirm"] = True
        if st.session_state.get(f"{name}_confirm"):
            unanswered = len(quiz.items) - n_answered
            msg = f"You have {unanswered} unanswered question(s). " if unanswered else ""
            st.warning(msg + "Submit the exam?")
            c = st.columns(2)
            if c[0].button("Yes, submit", key=f"{name}_yes"):
                st.session_state[f"{name}_confirm"] = False
                finish_quiz(quiz)
                st.rerun()
            if c[1].button("Keep working", key=f"{name}_no"):
                st.session_state[f"{name}_confirm"] = False
                st.rerun()

        with st.expander("Jump to question"):
            cols = st.columns(10)
            for i, it in enumerate(quiz.items):
                label = f"{i + 1}{'•' if it.answered else ''}"
                if cols[i % 10].button(label, key=f"{name}_jump_{i}", use_container_width=True):
                    quiz.index = i
                    st.rerun()

    if st.button("Quit this set", key=f"{name}_quit"):
        finish_quiz(quiz, record_exam=False)  # keep answers, don't log a partial exam score
        del st.session_state[quiz_key(name)]
        st.rerun()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_dashboard():
    st.title("📚 LCSW Study Buddy")
    st.write(
        "Practice for the **ASWB Clinical** exam. The real exam has "
        f"{EXAM_QUESTIONS} multiple-choice questions (150 scored) in {EXAM_MINUTES // 60} hours."
    )
    p = progress()
    stats = p.area_stats()
    total = sum(s["total"] for s in stats.values())
    correct = sum(s["correct"] for s in stats.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("Questions answered", total)
    c2.metric("Overall accuracy", f"{correct / total:.0%}" if total else "—")
    c3.metric("Bank coverage", f"{len(p.seen_ids() & Q_BY_ID.keys())} / {len(QUESTIONS)}")

    st.subheader("Your accuracy by exam content area")
    weakest, weakest_gap = None, -1.0
    for code, info in CONTENT_AREAS.items():
        s = stats.get(code)
        n_bank = sum(q.area == code for q in QUESTIONS)
        if s and s["total"]:
            st.progress(
                s["pct"] / 100,
                text=f"**{info['short']}** ({info['weight']:.0%} of exam): "
                f"{s['pct']:.0f}% on {int(s['total'])} attempts",
            )
            # Prioritize areas that are both weak and heavily weighted.
            gap = max(0, TARGET_PCT - s["pct"]) * info["weight"]
            if gap > weakest_gap:
                weakest, weakest_gap = code, gap
        else:
            st.progress(0.0, text=f"**{info['short']}** ({info['weight']:.0%} of exam): not started · {n_bank} questions")

    if total == 0:
        st.info("Start with **Practice** to get instant feedback, or try a short **Mock Exam** to find your baseline.")
    elif weakest and weakest_gap > 0:
        st.warning(f"**Suggested focus:** {CONTENT_AREAS[weakest]['name']}. It's below target and carries a lot of exam weight.")
    else:
        st.success("You're at or above target in every area you've practiced. Try a longer timed mock exam.")

    exams = p.data["exams"]
    if exams:
        st.subheader("Mock exam history")
        st.line_chart([round(e["pct"], 1) for e in exams], height=180)
        st.caption(f"Last {min(len(exams), 10)} shown below.")
        for e in reversed(exams[-10:]):
            when = time.strftime("%b %d, %Y %I:%M %p", time.localtime(e["ts"]))
            st.write(f"- {when}: **{e['pct']:.0f}%** ({e['correct']}/{e['total']})")

    missed = p.missed_ids() & Q_BY_ID.keys()
    if missed:
        st.caption(f"🔁 {len(missed)} question(s) in your review pile. Open **Review Missed** to work them.")


def page_practice():
    st.title("🎯 Practice")
    name = "practice"
    if quiz_key(name) in st.session_state:
        render_quiz(name)
        return
    st.write("Answer questions one at a time and get explanations right away.")
    areas = st.multiselect(
        "Content areas (leave empty for all)",
        list(CONTENT_AREAS),
        format_func=lambda a: CONTENT_AREAS[a]["name"],
    )
    pool = [q for q in QUESTIONS if not areas or q.area in areas]
    unseen_only = st.checkbox("Only questions I haven't answered yet")
    if unseen_only:
        seen = progress().seen_ids()
        pool = [q for q in pool if q.id not in seen]
    if not pool:
        st.info("No questions match. Try different areas or turn off 'unseen only'.")
        return
    count = st.slider("Number of questions", 1, len(pool), min(10, len(pool)))
    if st.button("Start practice", type="primary"):
        qs = build_practice(pool, None, count, rng())
        st.session_state[quiz_key(name)] = Quiz.create("practice", qs, rng())
        st.rerun()


def page_exam():
    st.title("📝 Mock Exam")
    name = "exam"
    if quiz_key(name) in st.session_state:
        render_quiz(name)
        return
    st.write(
        "Questions are drawn in proportion to the ASWB content outline. "
        "You won't see answers until you submit, just like the real exam."
    )
    for info in CONTENT_AREAS.values():
        st.caption(f"• {info['name']}: {info['weight']:.0%}")
    max_q = len(QUESTIONS)
    count = st.slider("Number of questions", 5, max_q, min(40, max_q), step=1)
    timed = st.checkbox(
        f"Timed at real-exam pace ({MINUTES_PER_QUESTION:.2f} min per question)", value=True
    )
    limit = count * MINUTES_PER_QUESTION * 60 if timed else None
    if timed:
        st.caption(f"Time limit: {fmt_secs(limit)}")
    if count < max_q:
        st.caption(f"The bank has {max_q} questions. Full-length (170) simulation needs a bigger bank; see the README.")
    if st.button("Start exam", type="primary"):
        qs = build_weighted_exam(QUESTIONS, count, rng())
        st.session_state[quiz_key(name)] = Quiz.create(
            "exam", qs, rng(), time_limit_s=limit, started_at=time.time()
        )
        st.rerun()


def page_review():
    st.title("🔁 Review Missed")
    name = "review"
    if quiz_key(name) in st.session_state:
        render_quiz(name)
        return
    missed = progress().missed_ids() & Q_BY_ID.keys()
    if not missed:
        st.success("Nothing to review. Questions you get wrong will show up here until you get them right.")
        return
    st.write(f"You have **{len(missed)}** question(s) whose most recent attempt was wrong.")
    by_area = {}
    for qid in missed:
        by_area.setdefault(Q_BY_ID[qid].area, 0)
        by_area[Q_BY_ID[qid].area] += 1
    for a, n in sorted(by_area.items()):
        st.caption(f"• {area_label(a)}: {n}")
    if st.button("Review them now", type="primary"):
        qs = build_practice(QUESTIONS, None, len(missed), rng(), only_ids=missed)
        st.session_state[quiz_key(name)] = Quiz.create("review", qs, rng())
        st.rerun()


def page_flashcards():
    st.title("🃏 Flashcards")
    st.caption(
        "Spaced repetition (Leitner boxes): cards you know move up a box and show up less often; "
        "cards you miss go back to box 1."
    )
    p = progress()
    areas = st.multiselect(
        "Content areas (leave empty for all)",
        list(CONTENT_AREAS),
        format_func=lambda a: CONTENT_AREAS[a]["name"],
        key="fc_areas",
    )
    ids = [c.id for c in CARDS if not areas or c.area in areas]
    if not ids:
        st.info("No cards in that selection.")
        return

    cur = st.session_state.get("fc_current")
    if cur not in ids:
        cur = p.next_card(ids, rng())
        st.session_state.fc_current = cur
        st.session_state.fc_flipped = False
    card = CARD_BY_ID[cur]

    with st.container(border=True):
        st.caption(f"{area_label(card.area)} · Box {p.card_box(card.id)} of {MAX_BOX}")
        st.markdown(f"### {card.term}")
        if st.session_state.get("fc_flipped"):
            st.markdown(card.definition)

    def advance(knew: bool | None):
        if knew is not None:
            p.grade_card(card.id, knew)
            p.save()
        st.session_state.fc_current = p.next_card(ids, rng(), exclude=card.id)
        st.session_state.fc_flipped = False

    if not st.session_state.get("fc_flipped"):
        c = st.columns(2)
        if c[0].button("Show answer", type="primary", use_container_width=True):
            st.session_state.fc_flipped = True
            st.rerun()
        if c[1].button("Skip", use_container_width=True):
            advance(None)
            st.rerun()
    else:
        c = st.columns(2)
        if c[0].button("✅ Knew it", type="primary", use_container_width=True):
            advance(True)
            st.rerun()
        if c[1].button("❌ Didn't know", use_container_width=True):
            advance(False)
            st.rerun()

    boxes = [p.card_box(i) for i in ids]
    st.caption(
        "Deck: " + " · ".join(f"Box {b}: {boxes.count(b)}" for b in range(1, MAX_BOX + 1))
    )


def page_data():
    st.title("💾 Your Data")
    p = progress()
    st.write(
        "Progress is saved to `progress.json` next to the app. If you use the app on a hosted "
        "service (like Streamlit Community Cloud), that file can be wiped when the app restarts, "
        "so **download a backup** regularly."
    )
    st.download_button(
        "⬇️ Download progress backup",
        p.to_json(),
        file_name="lcsw_progress.json",
        mime="application/json",
    )
    up = st.file_uploader("Restore from a backup", type="json")
    if up is not None and st.button("Restore this backup"):
        try:
            p.load_dict(json.loads(up.getvalue().decode("utf-8")))
            p.save()
            st.success("Progress restored.")
        except (ValueError, UnicodeDecodeError) as e:
            st.error(f"Couldn't read that file: {e}")

    st.divider()
    st.subheader("Reset")
    if st.checkbox("I understand this erases all my progress"):
        if st.button("Erase all progress", type="secondary"):
            p.reset()
            st.success("Progress erased.")

    st.divider()
    st.subheader("About the question bank")
    st.write(
        f"{len(QUESTIONS)} practice questions and {len(CARDS)} flashcards. "
        "These are original study questions written to the ASWB content outline. They are "
        "**not** official ASWB items. Use them alongside the official ASWB practice test and a "
        "reputable prep course."
    )
    st.write(
        "To add your own questions, create a file like `data/questions_custom.json` "
        "using the same format as `data/questions.json`. It's picked up automatically."
    )


PAGES = {
    "🏠 Dashboard": page_dashboard,
    "🎯 Practice": page_practice,
    "📝 Mock Exam": page_exam,
    "🔁 Review Missed": page_review,
    "🃏 Flashcards": page_flashcards,
    "💾 Your Data": page_data,
}

with st.sidebar:
    st.header("LCSW Study Buddy")
    choice = st.radio("Go to", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.caption(
        "Not affiliated with ASWB. Content follows the ASWB Clinical exam outline, the "
        "DSM-5-TR, and the NASW Code of Ethics. Check your state board for licensing rules."
    )

PAGES[choice]()
