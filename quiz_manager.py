"""Quiz prompt, validation, Python-side scoring, and recommendation logic."""
import random

NUM_QUESTIONS = 5
WEAK_THRESHOLD = 60    # below this -> revise
STRONG_THRESHOLD = 80  # at or above this -> move forward


class QuizValidationError(ValueError):
    """The model's quiz did not match the required structure."""


def choose_difficulty(last_percentage):
    """Adapt quiz difficulty to the learner's previous result on this topic."""
    if last_percentage is None:
        return "appropriate for the learner's level"
    if last_percentage < WEAK_THRESHOLD:
        return "easier and more foundational, focused on core ideas the learner is likely missing"
    if last_percentage >= STRONG_THRESHOLD:
        return "slightly harder, including application-style questions"
    return "appropriate for the learner's level, with a mix of concepts"


def build_quiz_prompt(subject, level, topic, objectives, last_percentage=None,
                      num_questions=NUM_QUESTIONS) -> str:
    obj = "; ".join(objectives)
    return f"""You are a tutor writing a short multiple-choice quiz.

Subject: {subject}
Learner level: {level}
Topic: {topic}
Topic objectives: {obj}
Difficulty: {choose_difficulty(last_percentage)}

Rules:
- Write EXACTLY {num_questions} questions that test the topic objectives.
- Each question has exactly 4 distinct options and exactly one correct answer.
- "correct_answer" is the letter A, B, C or D matching the correct option.
- "explanation" is ONE short sentence on why the answer is correct, in language suited to the learner's level.
- Return ONLY valid JSON, no markdown:
{{"questions": [{{"question": "...", "options": ["...", "...", "...", "..."],
  "correct_answer": "A", "explanation": "..."}}]}}"""


def _answer_index(raw, options):
    if isinstance(raw, str):
        s = raw.strip()
        if s.upper() in ("A", "B", "C", "D"):
            return "ABCD".index(s.upper())
        if s in options:
            return options.index(s)
    raise QuizValidationError('Each question needs "correct_answer" as one letter A-D.')


def validate_quiz(data, num_questions=NUM_QUESTIONS, shuffle=True) -> list:
    """Validate the model's quiz; return questions as
    [{question, options, correct_index, explanation}]. Options are shuffled in Python."""
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise QuizValidationError('Quiz must be an object with a "questions" list.')
    raw = data["questions"]
    if len(raw) < num_questions:
        raise QuizValidationError(f"Expected {num_questions} questions but got {len(raw)}.")
    rng = random.Random()
    out = []
    for i, q in enumerate(raw[:num_questions], start=1):
        if not isinstance(q, dict):
            raise QuizValidationError(f"Question {i} must be an object.")
        text = str(q.get("question", "")).strip()
        options = q.get("options")
        if not text:
            raise QuizValidationError(f"Question {i} has no text.")
        if not isinstance(options, list) or len(options) != 4:
            raise QuizValidationError(f"Question {i} must have exactly 4 options.")
        options = [str(o).strip() for o in options]
        if any(not o for o in options) or len(set(o.lower() for o in options)) != 4:
            raise QuizValidationError(f"Question {i} options must be non-empty and distinct.")
        correct = _answer_index(q.get("correct_answer"), options)
        explanation = str(q.get("explanation", "")).strip()
        if not explanation:
            raise QuizValidationError(f"Question {i} needs an explanation.")
        order = list(range(4))
        if shuffle:
            rng.shuffle(order)  # avoid the LLM's positional bias
        out.append({
            "question": text,
            "options": [options[j] for j in order],
            "correct_index": order.index(correct),
            "explanation": explanation,
        })
    return out


def score_quiz(questions: list, answers: list) -> dict:
    """Score in Python from the answer key. answers[i] is the chosen option index (or None)."""
    details, score = [], 0
    for q, a in zip(questions, answers):
        ok = a is not None and a == q["correct_index"]
        score += int(ok)
        details.append({**q, "selected_index": a, "is_correct": ok})
    total = len(questions)
    return {"score": score, "total": total,
            "percentage": round(100.0 * score / total, 1) if total else 0.0,
            "details": details}


def status_for_score(percentage: float) -> str:
    if percentage < WEAK_THRESHOLD:
        return "needs_revision"
    if percentage >= STRONG_THRESHOLD:
        return "completed"
    return "in_progress"


def recommend(topic: str, percentage: float, attempt_number: int) -> dict:
    """Recommendation after a quiz. Deliberately avoids claiming mastery from one quiz."""
    if percentage < WEAK_THRESHOLD:
        return {"action": "revise",
                "message": f"You scored {percentage:.0f}% on '{topic}'. This topic is flagged for revision: "
                           "review the objectives and explanations below, then take another practice quiz."}
    if percentage < STRONG_THRESHOLD:
        return {"action": "practice",
                "message": f"You scored {percentage:.0f}% on '{topic}'. You're getting there. "
                           "Review the questions you missed and try one more quiz to firm things up."}
    extra = (" One quiz is a small sample, so revisit this topic again later to confirm it sticks."
             if attempt_number <= 1 else "")
    return {"action": "advance",
            "message": f"You scored {percentage:.0f}% on '{topic}'. That's a strong result. "
                       f"Move on to the next topic or try harder practice.{extra}"}


def next_action(topics: list) -> dict:
    """Pick the learner's next step from topic statuses (used by the dashboard)."""
    if not topics:
        return {"kind": "none", "topic": None, "message": "Create a study plan to get started."}
    weak = [t for t in topics if t["status"] == "needs_revision"]
    if weak:
        t = weak[0]
        return {"kind": "revise", "topic": t,
                "message": f"Revise Day {t['day']}: {t['title']} (last score {t['last_score']:.0f}%) and retake the quiz."}
    open_ = [t for t in topics if t["status"] in ("in_progress", "pending")]
    if open_:
        in_prog = [t for t in open_ if t["status"] == "in_progress"]
        t = (in_prog or open_)[0]
        verb = "Keep practising" if t["status"] == "in_progress" else "Start"
        return {"kind": "continue", "topic": t,
                "message": f"{verb} Day {t['day']}: {t['title']}."}
    return {"kind": "done", "topic": None,
            "message": "All topics are completed. Consider a mixed review quiz or generate a harder plan."}
