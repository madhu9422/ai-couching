"""AI Personalized Learning Coach - Streamlit UI."""
import uuid

import pandas as pd
import streamlit as st

import code_manager as cm
import database as db
import learning_plan as lp
import quiz_manager as qm
import ui_theme as ui
from ai_service import AIService, AIServiceError

st.set_page_config(page_title="AI Personalized Learning Coach", page_icon="🎓", layout="wide")

PAGES = ["Home", "Learner Setup", "Study Plan", "Practice Quiz", "Code Practice", "Progress Dashboard"]
STATUS_LABEL = {
    "pending": "⚪ Pending",
    "in_progress": "🟡 In progress",
    "completed": "🟢 Completed",
    "needs_revision": "🔴 Needs revision",
}

ui.inject_css()
ss = st.session_state
ss.setdefault("page", "Home")
ss.setdefault("selected_topic_id", None)
ss.setdefault("quiz", None)      # {"token", "topic_id", "questions"}
ss.setdefault("result", None)    # result of the most recent submission
ss.setdefault("plan_created", False)


def goto(page, topic_id=None):
    ss.page = page
    if topic_id is not None:
        ss.selected_topic_id = topic_id


def db_call(fn, *args, **kwargs):
    """Run a database function; show a friendly error and return None on failure."""
    try:
        return fn(*args, **kwargs)
    except db.DatabaseError as exc:
        st.error(f"{exc}. Please try again; if it persists, check that the database file is writable.")
        return None


try:
    db.init_db()
except db.DatabaseError as exc:
    st.error(f"Could not open the database: {exc}")
    st.stop()


@st.cache_resource
def get_ai() -> AIService:
    return AIService()


ai = get_ai()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    ui.brand()
    st.radio("Navigate", PAGES, key="page")
    if not ai.has_api_key:
        st.warning("No API key found. Add GEMINI_API_KEY to your .env file.")
    else:
        st.caption(f"Model: {ai.model}")
    ui.sidebar_credit()


# ------------------------------------------------------------------ shared UI
def plan_form(defaults: dict, form_key: str, button_label: str):
    """Learner setup form (FR-01). Used for first setup and for regenerating (FR-03)."""
    with st.form(form_key):
        subject = st.text_input("Subject", value=defaults.get("subject", ""), placeholder="e.g. Python, Statistics, SQL")
        goal = st.text_area("Learning goal", value=defaults.get("goal", ""),
                            placeholder="e.g. Learn the fundamentals well enough to build small programs")
        c1, c2, c3 = st.columns(3)
        level_default = defaults.get("level", lp.LEVELS[0])
        level = c1.selectbox("Current level", lp.LEVELS, index=lp.LEVELS.index(level_default))
        days = c2.number_input("Target duration (days)", min_value=1, max_value=lp.MAX_DAYS,
                               value=int(defaults.get("duration_days", 7)), step=1)
        minutes = c3.number_input("Daily study time (minutes)", min_value=10, max_value=480,
                                  value=int(defaults.get("daily_minutes", 45)), step=5)
        submitted = st.form_submit_button(button_label, type="primary")

    if not submitted:
        return
    profile, errors = lp.validate_profile(subject, goal, level, days, minutes)
    if errors:
        for e in errors:
            st.error(e)
        return
    try:
        with st.spinner("Designing your personalised study plan..."):
            plan = ai.generate_plan(profile)
    except AIServiceError as exc:
        st.error(str(exc))
        st.info("You can press the button again to retry.")
        return
    plan_id = db_call(db.create_plan, profile, plan)
    if plan_id is None:
        return
    ss.quiz, ss.result, ss.selected_topic_id = None, None, None
    st.success(f"Your plan '{plan['title']}' is ready and saved!")
    st.button("View study plan →", on_click=goto, args=("Study Plan",), key=f"view_{form_key}")


def load_plan():
    plan = db_call(db.get_active_plan)
    if not plan:
        return None, []
    topics = db_call(db.get_topics, plan["id"]) or []
    return plan, topics


# ------------------------------------------------------------------ pages
def page_home():
    ui.hero("AI-POWERED LEARNING", "Learn smarter with a coach that adapts to you",
            "Tell the coach what you want to learn and how much time you have. It builds a day-by-day "
            "study plan, quizzes you on each topic, spots weak areas and tracks your progress.")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.info_card("1", "Set up", "Share your subject, goal, level and daily study time.")
    with c2:
        ui.info_card("2", "Practise", "Take AI-written quizzes that are scored fairly by Python.")
    with c3:
        ui.info_card("3", "Improve", "Get weak-topic flags and clear next-step recommendations.")
    plan, _ = load_plan()
    if plan:
        st.info(f"Active plan: **{plan['title']}**")
        st.button("Continue to dashboard →", type="primary", on_click=goto, args=("Progress Dashboard",))
    else:
        st.button("Get started →", type="primary", on_click=goto, args=("Learner Setup",))


def page_setup():
    ui.page_header("Learner Setup", "Tell the coach about your goal and schedule to generate a new study plan.")
    plan_form({}, "setup_form", "Generate my study plan")


def page_plan():
    ui.page_header("Study Plan", "Your personalised day-by-day roadmap")
    plan, topics = load_plan()
    if not plan:
        st.info("You don't have a plan yet.")
        st.button("Create a plan", on_click=goto, args=("Learner Setup",))
        return
    st.subheader(plan["title"])
    if plan["summary"]:
        st.write(plan["summary"])
    ui.chips([plan["subject"], plan["level"], f"{plan['duration_days']} days", f"{plan['daily_minutes']} min/day"])
    st.caption(f"Goal: {plan['goal']}")
    for t in topics:
        label = f"Day {t['day']}: {t['title']}  ·  {t['estimated_minutes']} min  ·  {STATUS_LABEL[t['status']]}"
        with st.expander(label):
            st.markdown("**Objectives**")
            st.markdown("\n".join(f"- {o}" for o in t["objectives"]))
            st.markdown("**Practice activities**")
            st.markdown("\n".join(f"- {a}" for a in t["activities"]))
            b1, b2, _ = st.columns([1, 1, 3])
            b1.button("📝 Take quiz", key=f"practice_{t['id']}", on_click=goto, args=("Practice Quiz", t["id"]))
            b2.button("💻 Code practice", key=f"code_{t['id']}", on_click=goto, args=("Code Practice", t["id"]))
    with st.expander("Adjust goal or schedule (regenerate plan)"):
        st.caption("This creates a new plan. Your earlier plans and quiz history stay saved.")
        plan_form(plan, "regen_form", "Regenerate plan")
    plans = db_call(db.list_plans) or []
    if len(plans) > 1:
        with st.expander("Previous plans"):
            for p in plans:
                c1, c2 = st.columns([4, 1])
                c1.write(f"{'✅ ' if p['is_active'] else ''}{p['title']} ({p['created_at'][:10]})")
                if not p["is_active"]:
                    c2.button("Switch", key=f"switch_{p['id']}",
                              on_click=lambda pid=p["id"]: (db.set_active_plan(pid), ss.update(quiz=None, result=None)))


def show_result(result: dict):
    st.subheader(f"Score: {result['score']} / {result['total']}  ({result['percentage']:.0f}%)")
    rec = result["recommendation"]
    {"revise": st.error, "practice": st.warning, "advance": st.success}[rec["action"]](rec["message"])
    if result.get("coach_note"):
        st.info(f"**Coach's note:** {result['coach_note']}")
    elif any(not d["is_correct"] for d in result["details"]):
        if st.button("💡 Get an AI coaching tip"):
            with st.spinner("Writing your tip..."):
                note = ai.generate_feedback(result["subject"], result["level"], result["topic_title"],
                                            result["details"], result["percentage"])
            result["coach_note"] = note or "Couldn't fetch a tip right now. Review the explanations below."
            st.rerun()
    st.markdown("### Review your answers")
    for i, d in enumerate(result["details"], start=1):
        icon = "✅" if d["is_correct"] else "❌"
        with st.expander(f"{icon} Question {i}: {d['question']}", expanded=not d["is_correct"]):
            sel = d["selected_index"]
            st.write(f"**Your answer:** {d['options'][sel] if sel is not None else '(not answered)'}")
            st.write(f"**Correct answer:** {d['options'][d['correct_index']]}")
            st.write(f"**Explanation:** {d['explanation']}")
    c1, c2 = st.columns(2)
    c1.button("Take another quiz on this topic", on_click=lambda: ss.update(quiz=None, result=None))
    c2.button("View progress dashboard", on_click=goto, args=("Progress Dashboard",))


def page_quiz():
    ui.page_header("Practice Quiz", "Test yourself on a topic and get instant feedback")
    plan, topics = load_plan()
    if not plan or not topics:
        st.info("Create a study plan first.")
        st.button("Create a plan", on_click=goto, args=("Learner Setup",))
        return
    ids = [t["id"] for t in topics]
    by_id = {t["id"]: t for t in topics}
    if ss.selected_topic_id not in ids:
        ss.selected_topic_id = ids[0]
    chosen = st.selectbox(
        "Choose a topic", ids, index=ids.index(ss.selected_topic_id),
        format_func=lambda i: f"Day {by_id[i]['day']}: {by_id[i]['title']}  ({STATUS_LABEL[by_id[i]['status']]})",
    )
    ss.selected_topic_id = chosen
    topic = by_id[chosen]

    if ss.result and ss.result["topic_id"] == chosen:
        show_result(ss.result)
        return

    if st.button("Generate quiz", type="primary"):
        try:
            with st.spinner("Writing your quiz..."):
                questions = ai.generate_quiz(plan["subject"], plan["level"], topic["title"],
                                             topic["objectives"], topic["last_score"])
            ss.quiz = {"token": uuid.uuid4().hex[:8], "topic_id": chosen, "questions": questions}
            ss.result = None
        except AIServiceError as exc:
            st.error(str(exc))
            st.info("Press 'Generate quiz' to retry.")

    quiz = ss.quiz
    if not quiz or quiz["topic_id"] != chosen:
        st.caption("Press **Generate quiz** to get five questions on this topic.")
        return

    st.subheader(f"Quiz: {topic['title']}")
    with st.form(f"quiz_form_{quiz['token']}"):
        answers = []
        for i, q in enumerate(quiz["questions"]):
            answers.append(st.radio(
                f"**{i + 1}. {q['question']}**", options=[0, 1, 2, 3], index=None,
                format_func=lambda j, opts=q["options"]: f"{'ABCD'[j]}. {opts[j]}",
                key=f"q_{quiz['token']}_{i}",
            ))
        submitted = st.form_submit_button("Submit answers", type="primary")
    if not submitted:
        return
    if any(a is None for a in answers):
        st.warning("Please answer every question before submitting.")
        return

    result = qm.score_quiz(quiz["questions"], answers)   # scored by Python, not the LLM
    attempt_no = topic["attempts"] + 1
    saved = db_call(db.record_attempt, chosen, plan["id"], quiz["questions"], answers,
                    result["score"], result["total"], qm.status_for_score(result["percentage"]))
    if saved is None:
        return
    result.update(topic_id=chosen, coach_note="", subject=plan["subject"], level=plan["level"],
                  topic_title=topic["title"],
                  recommendation=qm.recommend(topic["title"], result["percentage"], attempt_no))
    ss.result = result
    ss.quiz = None
    st.rerun()


def page_code():
    ui.page_header("Code Practice", "Python exercises matched to your skill level. Your code is run against test cases.")
    plan, topics = load_plan()
    if not plan or not topics:
        st.info("Create a study plan first.")
        st.button("Create a plan", on_click=goto, args=("Learner Setup",))
        return
    ids = [t["id"] for t in topics]
    by_id = {t["id"]: t for t in topics}
    if ss.selected_topic_id not in ids:
        ss.selected_topic_id = ids[0]
    chosen = st.selectbox("Choose a topic", ids, index=ids.index(ss.selected_topic_id),
                          format_func=lambda i: f"Day {by_id[i]['day']}: {by_id[i]['title']}", key="code_topic")
    ss.selected_topic_id = chosen
    topic = by_id[chosen]

    last = (db_call(db.get_code_attempts, plan["id"], chosen, 1) or [None])[0]
    auto = cm.choose_code_difficulty(plan["level"], last)
    c1, c2 = st.columns([2, 1])
    choice = c1.selectbox("Difficulty", ["Auto (matched to my skill)", "Easy", "Medium", "Hard"], key="code_diff")
    difficulty = auto if choice.startswith("Auto") else choice.lower()
    c2.markdown(f"<br>Suggested for you: **{auto}**", unsafe_allow_html=True)

    if st.button("Generate exercise", type="primary"):
        try:
            with st.spinner("Creating and verifying your exercise..."):
                ex = ai.generate_exercise(plan["subject"], plan["level"], topic["title"],
                                          topic["objectives"], difficulty)
            ss.code_ex = {"token": uuid.uuid4().hex[:8], "topic_id": chosen, "exercise": ex}
            ss.code_result = None
        except AIServiceError as exc:
            st.error(str(exc))
            st.info("Press 'Generate exercise' to retry.")

    state = ss.get("code_ex")
    if not state or state["topic_id"] != chosen:
        st.caption("Press **Generate exercise** to get a coding task for this topic.")
        return
    ex, token = state["exercise"], state["token"]

    st.markdown(f"### {ex['title']}")
    ui.chips([ex["difficulty"].capitalize(), f"Day {topic['day']}: {topic['title']}", f"{len(ex['tests'])} tests"])
    st.markdown(ex["description"])
    if ex["hint"]:
        with st.expander("💡 Hint"):
            st.write(ex["hint"])
    code = st.text_area("Your solution (Python)", value=ex["starter_code"], height=300, key=f"codebox_{token}")
    if st.button("▶ Run tests & submit", type="primary", key=f"run_{token}"):
        if not code.strip():
            st.warning("Write some code first.")
        else:
            with st.spinner("Running your code..."):
                res = cm.run_tests(code, ex["function_name"], ex["tests"])
            db_call(db.record_code_attempt, chosen, plan["id"], ex["title"], ex["difficulty"],
                    res["passed"], res["total"], code)
            ss.code_result = {"token": token, "res": res}

    out = ss.get("code_result")
    if out and out["token"] == token:
        res = out["res"]
        st.markdown(f"#### Result: {res['passed']} / {res['total']} tests passed")
        (st.success if res["passed"] == res["total"] else st.warning)(cm.code_recommendation(res["passed"], res["total"]))
        if res.get("fatal"):
            st.error(res["fatal"])
        for i, c in enumerate(res["cases"], 1):
            call = f"{ex['function_name']}({', '.join(repr(a) for a in c['args'])})"
            with st.expander(f"{'✅' if c['ok'] else '❌'} Test {i}: {call}", expanded=not c["ok"]):
                st.code(f"expected: {c['expected']!r}\ngot:      {c.get('error') or c['got']}", language="text")
        if res.get("stdout", "").strip():
            with st.expander("Your program's printed output"):
                st.code(res["stdout"], language="text")
        with st.expander("Reference solution"):
            st.code(ex["solution"], language="python")


def page_dashboard():
    plan, topics = load_plan()
    if not plan:
        ui.page_header("Progress Dashboard", "Track your learning journey")
        st.info("No progress yet. Create a plan to get started.")
        st.button("Create a plan", on_click=goto, args=("Learner Setup",))
        return
    attempts = db_call(db.get_attempts, plan["id"]) or []
    total = len(topics)
    done = sum(t["status"] == "completed" for t in topics)
    pending = sum(t["status"] == "pending" for t in topics)
    recent = attempts[:5]
    avg = sum(a["percentage"] for a in recent) / len(recent) if recent else None

    ui.page_header("Progress Dashboard", f"{plan['title']} · {plan['subject']} · {plan['level']}")
    k = st.columns(4)
    k[0].markdown(ui.kpi("✅", "Completed", f"{done} / {total}", "#34D399"), unsafe_allow_html=True)
    k[1].markdown(ui.kpi("⏳", "Pending", pending, "#FBBF24"), unsafe_allow_html=True)
    k[2].markdown(ui.kpi("📝", "Quizzes taken", len(attempts), "#6C8CFF"), unsafe_allow_html=True)
    k[3].markdown(ui.kpi("🎯", "Recent average", f"{avg:.0f}%" if avg is not None else "—", "#A855F7"),
                  unsafe_allow_html=True)
    st.write("")

    action = qm.next_action(topics)
    left, right = st.columns([1, 1.4])
    left.markdown(ui.ring_card(100 * done / total if total else 0, f"{done} of {total} topics completed"),
                  unsafe_allow_html=True)
    right.markdown(ui.next_card(action["kind"], action["message"]), unsafe_allow_html=True)
    if action["topic"]:
        right.button("Practice this topic now →", type="primary", on_click=goto,
                     args=("Practice Quiz", action["topic"]["id"]))

    weak = [t for t in topics if t["status"] == "needs_revision"]
    if weak:
        st.markdown("### Flagged for revision")
        for t in weak:
            st.warning(f"Day {t['day']}: **{t['title']}**, last score {t['last_score']:.0f}%")

    st.markdown("### Learning roadmap")
    ui.render("".join(ui.topic_row(t, STATUS_LABEL[t["status"]].split(" ", 1)[1]) for t in topics))

    code_attempts = db_call(db.get_code_attempts, plan["id"], None, 8) or []
    if code_attempts:
        st.markdown("### Code practice")
        st.dataframe(pd.DataFrame([{
            "Date": c["created_at"].replace("T", " "), "Topic": f"Day {c['day']}: {c['topic_title']}",
            "Exercise": c["title"], "Level": c["difficulty"].capitalize(), "Tests passed": f"{c['passed']}/{c['total']}",
        } for c in code_attempts]), hide_index=True)

    st.markdown("### Quiz history")
    if not attempts:
        st.caption("No quizzes yet. Take your first quiz from the Practice Quiz page.")
        return
    if len(attempts) >= 2:
        chart = pd.DataFrame({"Score %": [a["percentage"] for a in reversed(attempts)]})
        chart.index = range(1, len(chart) + 1)
        chart.index.name = "Attempt"
        st.area_chart(chart, color="#6C8CFF", height=240)
    st.dataframe(pd.DataFrame([{
        "Date": a["created_at"].replace("T", " "), "Topic": f"Day {a['day']}: {a['topic_title']}",
        "Score": f"{a['score']}/{a['total']}", "Percent": f"{a['percentage']:.0f}%",
    } for a in attempts]), hide_index=True)


{
    "Home": page_home,
    "Learner Setup": page_setup,
    "Study Plan": page_plan,
    "Practice Quiz": page_quiz,
    "Code Practice": page_code,
    "Progress Dashboard": page_dashboard,
}[ss.page]()
ui.footer()
