"""Code practice: exercise prompt/validation, sandboxed test runner, difficulty by skill.

Learner code runs in a separate Python process with a time limit and a minimal environment
(your API key is NOT passed to it). It is still your own machine, so only run code you wrote.
Scoring is done in Python by comparing return values with the test cases, never by the LLM.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

DIFFICULTIES = ["easy", "medium", "hard"]
_LEVEL_START = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
_DIFF_DESC = {
    "easy": "easy: a short function (1-5 lines), one core idea, a clear example",
    "medium": "medium: combines two ideas, handles a few edge cases, around 5-12 lines",
    "hard": "hard: needs planning, several edge cases or an efficient approach, 10-20 lines",
}


class CodeValidationError(ValueError):
    """The model's exercise did not match the required structure or failed its own tests."""


# ----------------------------------------------------------------- skill-based difficulty
def choose_code_difficulty(level: str, last_attempt=None) -> str:
    """Start at the learner's level; then move up after a perfect run and down after a weak one."""
    if not last_attempt:
        return DIFFICULTIES[_LEVEL_START.get(level, 0)]
    idx = DIFFICULTIES.index(last_attempt["difficulty"]) if last_attempt["difficulty"] in DIFFICULTIES else 0
    rate = last_attempt["passed"] / last_attempt["total"] if last_attempt["total"] else 0
    if rate == 1:
        idx = min(idx + 1, 2)
    elif rate < 0.5:
        idx = max(idx - 1, 0)
    return DIFFICULTIES[idx]


def build_exercise_prompt(subject, level, topic, objectives, difficulty) -> str:
    obj = "; ".join(objectives)
    return f"""You are a programming instructor. Create ONE Python coding exercise.

Subject: {subject}
Learner level: {level}
Topic: {topic}
Objectives: {obj}
Difficulty: {_DIFF_DESC.get(difficulty, difficulty)}

Rules:
- The learner writes ONE function. Choose a clear snake_case "function_name".
- The function takes arguments and RETURNS a value. No input(), print(), files or network.
- Give 4-6 "tests" covering normal cases and edge cases. "args" is a JSON list of the arguments and
  "expected" is the exact JSON return value (use lists, never tuples or sets).
- "starter_code" has the def line, a one-line docstring and `pass` as the body.
- "solution" is a correct, complete implementation that passes every test.
- "description" is 2-4 sentences and includes one worked example. "hint" is one sentence.
- If the subject is not programming, apply the topic through a small Python exercise.
- Keep everything concise. Return ONLY valid JSON, no markdown:
{{"title": "...", "description": "...", "function_name": "...", "starter_code": "def ...",
  "hint": "...", "solution": "def ...", "tests": [{{"args": [], "expected": null}}]}}"""


# ----------------------------------------------------------------- sandboxed runner
_RUNNER = r'''
import json, sys
MARK = "__CODE_RESULT__"

def _norm(x):
    def conv(o):
        if isinstance(o, (set, frozenset)):
            return sorted(o, key=repr)
        if isinstance(o, tuple):
            return list(o)
        return repr(o)
    try:
        return json.loads(json.dumps(x, default=conv))
    except Exception:
        return repr(x)

def _eq(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except Exception:
            return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
    return a == b

def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = {"cases": []}
    ns = {"__name__": "__learner__"}
    try:
        exec(compile(spec["code"], "<your code>", "exec"), ns)
    except BaseException as e:
        out["fatal"] = type(e).__name__ + ": " + str(e)
        print(MARK + json.dumps(out)); return
    fn = ns.get(spec["function_name"])
    if not callable(fn):
        out["fatal"] = "Your code must define a function named " + spec["function_name"] + "()."
        print(MARK + json.dumps(out)); return
    for case in spec["tests"]:
        try:
            got = fn(*json.loads(json.dumps(case["args"])))
            out["cases"].append({"ok": bool(_eq(_norm(got), _norm(case["expected"]))), "got": repr(got)[:200]})
        except BaseException as e:
            out["cases"].append({"ok": False, "got": None, "error": (type(e).__name__ + ": " + str(e))[:200]})
    print(MARK + json.dumps(out))

main()
'''
_MARK = "__CODE_RESULT__"


def _safe_env() -> dict:
    keep = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "HOME", "USERPROFILE")
    return {k: os.environ[k] for k in keep if k in os.environ}


def run_tests(code: str, function_name: str, tests: list, timeout: int = 8) -> dict:
    """Run learner code against tests. Returns {passed, total, cases, fatal?, stdout}."""
    total = len(tests)
    fail = lambda msg, out="": {"passed": 0, "total": total, "cases": [], "fatal": msg, "stdout": out}
    with tempfile.TemporaryDirectory() as d:
        runner, spec = os.path.join(d, "runner.py"), os.path.join(d, "spec.json")
        with open(runner, "w", encoding="utf-8") as f:
            f.write(_RUNNER)
        with open(spec, "w", encoding="utf-8") as f:
            json.dump({"code": code, "function_name": function_name, "tests": tests}, f)
        try:
            p = subprocess.run([sys.executable, "-I", runner, spec], capture_output=True, text=True,
                               timeout=timeout, cwd=d, env=_safe_env(), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return fail(f"Time limit exceeded ({timeout}s). Check for an infinite loop or very slow code.")
        except OSError as exc:
            return fail(f"Could not run your code: {exc}")
    stdout, marker, payload = p.stdout.rpartition(_MARK)
    if not marker:
        err = (p.stderr or "").strip().splitlines()
        return fail("Your code crashed before the tests finished. " + (err[-1] if err else ""), p.stdout[:1000])
    try:
        data = json.loads(payload.strip().splitlines()[0])
    except (ValueError, IndexError):
        return fail("Could not read the test results.")
    if "fatal" in data:
        return fail(data["fatal"], stdout[:1000])
    cases = data["cases"]
    for c, t in zip(cases, tests):
        c["args"], c["expected"] = t["args"], t["expected"]
    return {"passed": sum(c["ok"] for c in cases), "total": total, "cases": cases, "stdout": stdout[:1000]}


# ----------------------------------------------------------------- validation
def validate_exercise(data, difficulty: str = "easy") -> dict:
    """Validate the model's exercise AND check its answer key by running its own reference solution."""
    if not isinstance(data, dict):
        raise CodeValidationError("Exercise must be a JSON object.")
    get = lambda k: str(data.get(k) or "").strip()
    title, desc, fn = get("title"), get("description"), get("function_name")
    starter, solution = str(data.get("starter_code") or ""), str(data.get("solution") or "")
    if not title or not desc:
        raise CodeValidationError("Exercise needs a title and a description.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", fn):
        raise CodeValidationError("function_name must be a valid Python identifier.")
    if f"def {fn}" not in starter or f"def {fn}" not in solution:
        raise CodeValidationError(f"starter_code and solution must both define def {fn}(...).")
    tests = data.get("tests")
    if not isinstance(tests, list) or not 3 <= len(tests) <= 8:
        raise CodeValidationError("Provide between 3 and 8 test cases.")
    for i, t in enumerate(tests, 1):
        if not isinstance(t, dict) or not isinstance(t.get("args"), list) or "expected" not in t:
            raise CodeValidationError(f'Test {i} needs an "args" list and an "expected" value.')
    ref = run_tests(solution, fn, tests)
    if ref["passed"] != ref["total"]:
        raise CodeValidationError(
            f"The reference solution fails its own tests ({ref['passed']}/{ref['total']}); the tests or solution are wrong.")
    if run_tests(starter, fn, tests)["passed"] == len(tests):
        raise CodeValidationError("The starter code already solves the exercise.")
    return {"title": title[:120], "description": desc, "function_name": fn, "starter_code": starter,
            "hint": get("hint"), "solution": solution, "tests": tests, "difficulty": difficulty}


def code_recommendation(passed: int, total: int) -> str:
    if total and passed == total:
        return "All tests passed. Generate another exercise; it will get a little harder."
    if passed == 0:
        return "No tests passed yet. Re-read the description, check the hint, and trace the first example by hand."
    return f"{passed} of {total} tests passed. Look at the failing cases below, fix your logic and run again."
