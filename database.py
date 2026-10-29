"""SQLite persistence layer: learner profiles, plans, topics, quiz attempts."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

STATUSES = ("pending", "in_progress", "completed", "needs_revision")


class DatabaseError(Exception):
    """Raised for any database failure, with a user-friendly message."""


def _path() -> str:
    return os.getenv("DB_PATH", "learning_coach.db")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _connect():
    try:
        conn = sqlite3.connect(_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc


SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    goal TEXT NOT NULL,
    level TEXT NOT NULL,
    duration_days INTEGER NOT NULL,
    daily_minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    title TEXT NOT NULL,
    objectives_json TEXT NOT NULL,
    activities_json TEXT NOT NULL,
    estimated_minutes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_score REAL,
    best_score REAL,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    percentage REAL NOT NULL,
    questions_json TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS code_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    passed INTEGER NOT NULL,
    total INTEGER NOT NULL,
    code TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)


def _topic_row(row) -> dict:
    d = dict(row)
    d["objectives"] = json.loads(d.pop("objectives_json"))
    d["activities"] = json.loads(d.pop("activities_json"))
    return d


def create_plan(profile: dict, plan: dict) -> int:
    """Save learner + plan + topics; the new plan becomes the active one."""
    with _connect() as conn:
        now = _now()
        cur = conn.execute(
            "INSERT INTO learners (subject, goal, level, duration_days, daily_minutes, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (profile["subject"], profile["goal"], profile["level"],
             profile["duration_days"], profile["daily_minutes"], now),
        )
        learner_id = cur.lastrowid
        conn.execute("UPDATE plans SET is_active = 0")
        cur = conn.execute(
            "INSERT INTO plans (learner_id, title, summary, is_active, created_at) VALUES (?,?,?,1,?)",
            (learner_id, plan["title"], plan.get("summary", ""), now),
        )
        plan_id = cur.lastrowid
        for d in plan["days"]:
            conn.execute(
                "INSERT INTO topics (plan_id, day, title, objectives_json, activities_json, "
                "estimated_minutes, status, updated_at) VALUES (?,?,?,?,?,?,'pending',?)",
                (plan_id, d["day"], d["topic"], json.dumps(d["objectives"]),
                 json.dumps(d["activities"]), d["estimated_minutes"], now),
            )
        return plan_id


def get_active_plan():
    with _connect() as conn:
        row = conn.execute(
            "SELECT p.id, p.title, p.summary, p.created_at, l.subject, l.goal, l.level, "
            "l.duration_days, l.daily_minutes FROM plans p JOIN learners l ON l.id = p.learner_id "
            "WHERE p.is_active = 1 ORDER BY p.id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def list_plans() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT p.id, p.title, p.is_active, p.created_at, l.subject FROM plans p "
            "JOIN learners l ON l.id = p.learner_id ORDER BY p.id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def set_active_plan(plan_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE plans SET is_active = 0")
        conn.execute("UPDATE plans SET is_active = 1 WHERE id = ?", (plan_id,))


def get_topics(plan_id: int) -> list:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM topics WHERE plan_id = ? ORDER BY day", (plan_id,)).fetchall()
        return [_topic_row(r) for r in rows]


def get_topic(topic_id: int):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        return _topic_row(row) if row else None


def record_attempt(topic_id: int, plan_id: int, questions: list, answers: list,
                   score: int, total: int, new_status: str) -> int:
    """Save one quiz attempt (each attempt is a separate row) and update the topic."""
    if new_status not in STATUSES:
        raise DatabaseError(f"Invalid topic status: {new_status}")
    pct = round(100.0 * score / total, 1) if total else 0.0
    with _connect() as conn:
        now = _now()
        cur = conn.execute(
            "INSERT INTO quiz_attempts (topic_id, plan_id, score, total, percentage, "
            "questions_json, answers_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (topic_id, plan_id, score, total, pct, json.dumps(questions), json.dumps(answers), now),
        )
        conn.execute(
            "UPDATE topics SET status = ?, attempts = attempts + 1, last_score = ?, "
            "best_score = MAX(COALESCE(best_score, 0), ?), updated_at = ? WHERE id = ?",
            (new_status, pct, pct, now, topic_id),
        )
        return cur.lastrowid


def get_attempts(plan_id: int, topic_id: int = None, limit: int = None) -> list:
    sql = ("SELECT a.id, a.topic_id, a.score, a.total, a.percentage, a.created_at, "
           "t.title AS topic_title, t.day FROM quiz_attempts a JOIN topics t ON t.id = a.topic_id "
           "WHERE a.plan_id = ?")
    params = [plan_id]
    if topic_id is not None:
        sql += " AND a.topic_id = ?"
        params.append(topic_id)
    sql += " ORDER BY a.id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def record_code_attempt(topic_id, plan_id, title, difficulty, passed, total, code) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO code_attempts (topic_id, plan_id, title, difficulty, passed, total, code, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (topic_id, plan_id, title, difficulty, passed, total, code, _now()),
        )
        return cur.lastrowid


def get_code_attempts(plan_id: int, topic_id: int = None, limit: int = None) -> list:
    sql = ("SELECT c.id, c.topic_id, c.title, c.difficulty, c.passed, c.total, c.created_at, "
           "t.title AS topic_title, t.day FROM code_attempts c JOIN topics t ON t.id = c.topic_id "
           "WHERE c.plan_id = ?")
    params = [plan_id]
    if topic_id is not None:
        sql += " AND c.topic_id = ?"
        params.append(topic_id)
    sql += " ORDER BY c.id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
