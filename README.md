# 📚 LCSW Study Buddy

A Streamlit app for studying for the **ASWB Clinical exam**, the exam most states require for LCSW licensure.

## Features

| Page | What it does |
|---|---|
| **Dashboard** | Your accuracy in each of the 4 ASWB content areas, weighted by how much of the exam each area makes up. Suggests what to focus on next. Shows your mock exam score history. |
| **Practice** | Questions one at a time, with the correct answer and an explanation right after you answer. Filter by content area or show only questions you haven't seen. |
| **Mock Exam** | Questions drawn in proportion to the ASWB outline (24 / 30 / 27 / 19%). Optional timer at real exam pace (4 hours ÷ 170 questions ≈ 1.4 min per question). No feedback until you submit. |
| **Review Missed** | Every question you got wrong most recently. A question stays here until you answer it correctly. |
| **Flashcards** | 75 high-yield cards: DSM-5-TR duration cutoffs, developmental theories, defense mechanisms, therapy models, and NASW Code standards. Uses spaced repetition (Leitner boxes). |
| **Your Data** | Download/restore a progress backup, or reset. |

Answer choices are shuffled every time, so you learn the content instead of remembering "it was B."

## Run it

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Run the tests with `pip install pytest && pytest`.

## Important limitations

- **These are not official ASWB questions.** There are 79 original questions written to the ASWB content outline, DSM-5-TR, and the NASW Code of Ethics. Use them alongside the official ASWB practice test, which is the only source of real exam-calibrated items.
- **79 questions is not enough for full-length mock exams.** The real exam has 170. The bank is good for learning the content areas and question style, but you'll start recognizing questions after a few rounds. Add more (see below).
- **The ~70% target is an estimate.** ASWB's passing score is set separately for each exam form and isn't published as a fixed percentage.
- **Progress is saved to `progress.json`.** On hosted services such as Streamlit Community Cloud, that file is shared by everyone using the app and is erased when the app restarts. If you deploy it, use **Your Data → Download backup**, or run it locally.

## Adding your own questions

Create `data/questions_custom.json` (any `data/questions*.json` file is loaded automatically):

```json
[
  {
    "id": "my-001",
    "area": "ADT",
    "topic": "Bipolar disorders",
    "stem": "The question text...",
    "options": ["Correct answer", "Distractor", "Distractor", "Distractor"],
    "answer": 0,
    "explanation": "Why the correct answer is right and the others are wrong."
  }
]
```

`area` must be one of `HGD` (Human Development & Diversity), `ADT` (Assessment & Diagnosis), `PCI` (Interventions & Case Management), or `ETH` (Values & Ethics). `answer` is the index of the correct option; options are shuffled when shown, so putting the correct one first is fine. Flashcards work the same way with `data/flashcards*.json` (`id`, `area`, `term`, `definition`).

The tests check every question file for missing fields, duplicate IDs, and bad answer indexes. They also fail if the correct answer is the longest option much more often than chance, since that would let you guess without knowing the material.

## Project layout

```
streamlit_app.py     UI (all pages)
lcsw/content.py      content areas, exam constants, loading and validating questions/flashcards
lcsw/quiz.py         building weighted exams and practice sets, scoring
lcsw/progress.py     saved attempts, missed-question tracking, flashcard boxes
data/                question and flashcard banks (JSON)
tests/               logic tests plus headless UI tests (streamlit AppTest)
```
