# AI Personalized Learning Coach

A Streamlit web app that builds a personalised study plan with an LLM (Gemini), generates topic quizzes,
**scores them in Python**, flags weak topics, recommends next steps, and stores everything in SQLite.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then put your Gemini API key in .env
streamlit run app.py
```
Get a free key at https://aistudio.google.com/apikey. Run the tests with `python -m unittest discover -s tests -v`
(they use mocked LLM calls, so no key is needed).

## Project structure
| File | Responsibility |
|---|---|
| `ui_theme.py` | Dark professional theme: CSS, KPI cards, progress ring, roadmap rows |
| `app.py` | Streamlit UI: Home, Learner Setup, Study Plan, Practice Quiz, Progress Dashboard |
| `ai_service.py` | Gemini calls, JSON parsing, retry on API failure, re-prompt on invalid output |
| `learning_plan.py` | Input validation, plan prompt, plan validation (FR-01/02/03) |
| `quiz_manager.py` | Quiz prompt + validation, Python scoring, weak-topic logic, recommendations |
| `code_manager.py` | Code Practice: exercise prompt and validation, sandboxed test runner, skill-based difficulty |
| `check_api.py` | Tests which Gemini models work for your key and how fast they are |
| `database.py` | SQLite schema and queries |
| `tests/test_core.py` | Automated tests for the brief's test cases |
| `sample_data/example_learning_plan.json` | Format example only (never loaded by the app) |

## How it works
1. **Setup**: subject, goal, level, duration and daily time are validated (missing fields give clear messages).
2. **Plan**: the prompt asks for strict JSON with exactly *N* days. Python validates the structure, the day count, and caps each day's minutes to the daily time budget. An invalid reply triggers a re-prompt that includes the validation error (up to 3 tries).
3. **Quiz**: the LLM returns 5 questions with 4 options, a letter answer key and explanations. Python validates them and **shuffles the options** (to remove LLM position bias), keeping the answer key aligned.
4. **Scoring**: `quiz_manager.score_quiz` compares the learner's choices with the answer key. The LLM never calculates the score.
5. **Adaptation**: <60% marks the topic *needs revision*; 60-79% *in progress*; ≥80% *completed*. The next quiz on a topic adapts its difficulty to the previous score. A single high score gets a "revisit later" note, so mastery is never claimed from one quiz.
6. **Dashboard**: completed/pending counts, recent average, topic table, quiz history chart, weak topics and a next action.

## Code Practice (skill-based coding exercises)
- Pick a topic and press **Generate exercise**. Difficulty is **Auto**: it starts at your level (Beginner → easy,
  Intermediate → medium, Advanced → hard), moves up after a perfect run and down after a weak one. You can override it.
- You write a Python function, press **Run tests & submit**, and see which test cases pass or fail.
- Python runs your code in a separate process (8 s time limit, minimal environment, your API key is not passed to it) and
  compares return values with the test cases. The LLM never decides pass or fail.
- Each exercise is **verified before you see it**: the model's own reference solution is run against its tests, and the
  exercise is rejected (and regenerated) if it fails or if the starter code already solves it.
- Safety note: this runs code on your own computer. Only run code you wrote yourself.

## If the AI is slow or shows a 504 / timeout error
- Run `python check_api.py`. It tests the available flash models on your key and prints the fastest `GEMINI_MODEL=` line for `.env`.
- The app streams replies and automatically falls back to another available flash model when one times out or is unavailable
  (set your own order with `GEMINI_FALLBACK_MODELS=model-a,model-b`).
- Try a shorter plan (3-7 days) first; long plans need much more text from the model.

## Speed
- Model "thinking" is set to minimal (`GEMINI_THINKING=minimal`; set `default` to turn this off).
- Prompts ask for short plans and one-sentence explanations, so the model writes less.
- Quiz results appear instantly; the AI coaching tip is fetched only when you press the button.
- Code results come from local test runs, with no extra AI call.

## Database (SQLite, `learning_coach.db`)
- `learners(id, subject, goal, level, duration_days, daily_minutes, created_at)`
- `plans(id, learner_id→learners, title, summary, is_active, created_at)`
- `topics(id, plan_id→plans, day, title, objectives_json, activities_json, estimated_minutes, status, attempts, last_score, best_score, updated_at)`
- `code_attempts(id, topic_id→topics, plan_id→plans, title, difficulty, passed, total, code, created_at)`
- `quiz_attempts(id, topic_id→topics, plan_id→plans, score, total, percentage, questions_json, answers_json, created_at)`

Every attempt is a new row, so history is preserved. Regenerating a plan creates a new plan and keeps the old one.

## Error handling (FR-12)
Missing inputs → validation messages · no API key → setup instructions · API/network failure → retries with
backoff, then a friendly message with retry · invalid JSON/structure → automatic re-prompt, then error (no crash) ·
database errors → `DatabaseError` shown as a message · quiz submitted with unanswered questions → warning.
The optional coach's note fails silently so scoring and saving never depend on it.

## Limitations (for the viva)
- LLM-generated quiz questions can occasionally be inaccurate; there is no human review of the answer key.
- Five questions is a small sample, so scores are only a rough signal of understanding.
- Single local user, no login; the SQLite file lives on the machine running the app.
- Free API tiers have rate limits; the app retries but may still show an error under heavy use.
- Plan quality depends on the model and on how specific the learner's goal is.

## Suggested Git workflow
```bash
git init && git add . && git commit -m "Initial commit: AI Personalized Learning Coach"
git branch -M main && git remote add origin <your-repo-url> && git push -u origin main
```
`.env` and `*.db` are git-ignored, so your API key is never committed.
