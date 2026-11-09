"""Headless smoke tests that drive the real Streamlit UI."""

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("LCSW_PROGRESS_PATH", str(tmp_path / "progress.json"))
    at = AppTest.from_file("../streamlit_app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def goto(at, page):
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception


def click(at, label):
    [b for b in at.button if b.label == label][0].click().run()
    assert not at.exception


def test_every_page_renders(app):
    for page in ["🏠 Dashboard", "🎯 Practice", "📝 Mock Exam", "🔁 Review Missed", "🃏 Flashcards", "💾 Your Data"]:
        goto(app, page)


def test_practice_flow_records_progress(app):
    goto(app, "🎯 Practice")
    app.slider[0].set_value(2).run()
    click(app, "Start practice")
    for _ in range(2):
        app.main.radio[0].set_value(0).run()
        click(app, "Submit answer")
        assert app.info  # explanation shown
        nxt = [b for b in app.button if b.label in ("Next question →", "See results")][0]
        nxt.click().run()
    assert any("Results" in s.value for s in app.subheader)
    p = app.session_state["progress"]
    assert len(p.data["attempts"]) == 2


def test_exam_flow(app):
    goto(app, "📝 Mock Exam")
    app.slider[0].set_value(5).run()
    click(app, "Start exam")
    app.main.radio[0].set_value(1).run()
    click(app, "Finish exam")
    click(app, "Yes, submit")
    p = app.session_state["progress"]
    assert len(p.data["exams"]) == 1 and p.data["exams"][0]["total"] == 5
    assert p.data["exams"][0]["answered"] == 1


def test_flashcards(app):
    goto(app, "🃏 Flashcards")
    click(app, "Show answer")
    click(app, "✅ Knew it")
    assert any(v == 2 for v in app.session_state["progress"].data["cards"].values())
