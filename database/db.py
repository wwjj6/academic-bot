# -*- coding: utf-8 -*-
"""
طبقة قاعدة البيانات (SQLite) لبوت المسابقات الأكاديمية
كلية الطب | جامعة حجة
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

with open(_CONFIG_PATH, encoding="utf-8") as f:
    _cfg = json.load(f)

DB_PATH = os.path.join(os.path.dirname(_CONFIG_PATH), _cfg.get("database_path", "academic_bot.db"))

# ---------------------------------------------------------------- الاتصال --

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
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


def init_db():
    """إنشاء جميع الجداول إن لم تكن موجودة."""
    with get_conn() as conn:
        conn.executescript("""
        -- المستخدمون (جميع الأدوار)
        CREATE TABLE IF NOT EXISTS Users (
            user_id       INTEGER PRIMARY KEY,          -- Telegram ID
            full_name     TEXT NOT NULL,
            username      TEXT,
            role          TEXT NOT NULL DEFAULT 'student'
                          CHECK (role IN ('admin','professor','committee','student')),
            university_id TEXT,
            level         TEXT,
            joined_at     TEXT DEFAULT (datetime('now'))
        );

        -- المدرسون
        CREATE TABLE IF NOT EXISTS Professors (
            professor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL UNIQUE REFERENCES Users(user_id) ON DELETE CASCADE,
            degree       TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        -- المقررات الدراسية
        CREATE TABLE IF NOT EXISTS Subjects (
            subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            code       TEXT,
            level      TEXT
        );

        -- ربط المدرس بالمقررات (مدرس واحد -> عدة مقررات)
        CREATE TABLE IF NOT EXISTS Professor_Subjects (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_id INTEGER NOT NULL REFERENCES Professors(professor_id) ON DELETE CASCADE,
            subject_id   INTEGER NOT NULL REFERENCES Subjects(subject_id) ON DELETE CASCADE,
            assigned_at  TEXT DEFAULT (datetime('now')),
            UNIQUE (professor_id, subject_id)
        );

        -- تسجيل الطلاب في المقررات
        CREATE TABLE IF NOT EXISTS Student_Subjects (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
            subject_id INTEGER NOT NULL REFERENCES Subjects(subject_id) ON DELETE CASCADE,
            UNIQUE (user_id, subject_id)
        );

        -- المسابقات
        CREATE TABLE IF NOT EXISTS Competitions (
            competition_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT NOT NULL,
            subject_id       INTEGER REFERENCES Subjects(subject_id) ON DELETE CASCADE,  -- NULL = مسابقة عامة
            creator_id       INTEGER NOT NULL REFERENCES Users(user_id),
            comp_type        TEXT NOT NULL DEFAULT 'weekly'
                             CHECK (comp_type IN ('weekly','monthly','challenge','general')),
            num_questions    INTEGER NOT NULL,
            question_seconds INTEGER NOT NULL DEFAULT 60,
            start_time       TEXT,
            end_time         TEXT,
            status           TEXT NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft','pending_review','approved','active','closed','rejected')),
            created_at       TEXT DEFAULT (datetime('now'))
        );

        -- الأسئلة (اختيار من متعدد: أ، ب، ج، د)
        CREATE TABLE IF NOT EXISTS Questions (
            question_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER NOT NULL REFERENCES Competitions(competition_id) ON DELETE CASCADE,
            text           TEXT NOT NULL,
            option_a       TEXT NOT NULL,
            option_b       TEXT NOT NULL,
            option_c       TEXT NOT NULL,
            option_d       TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK (correct_option IN ('a','b','c','d')),
            status         TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','approved','rejected'))
        );

        -- إجابات الطلاب
        CREATE TABLE IF NOT EXISTS Answers (
            answer_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id     INTEGER NOT NULL REFERENCES Questions(question_id) ON DELETE CASCADE,
            user_id         INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
            selected_option TEXT,                        -- NULL = انتهى الوقت بلا إجابة
            is_correct      INTEGER NOT NULL DEFAULT 0,
            answered_at     TEXT DEFAULT (datetime('now')),
            UNIQUE (question_id, user_id)
        );

        -- النتائج النهائية
        CREATE TABLE IF NOT EXISTS Results (
            result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER NOT NULL REFERENCES Competitions(competition_id) ON DELETE CASCADE,
            user_id        INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
            score          INTEGER NOT NULL,
            total          INTEGER NOT NULL,
            time_taken     INTEGER NOT NULL DEFAULT 0,   -- بالثواني
            finished_at    TEXT DEFAULT (datetime('now')),
            UNIQUE (competition_id, user_id)
        );

        -- الترتيب العام (نقاط تراكمية لكل مقرر، وNULL = الترتيب العام)
        CREATE TABLE IF NOT EXISTS Leaderboard (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
            subject_id INTEGER REFERENCES Subjects(subject_id) ON DELETE CASCADE,
            points     INTEGER NOT NULL DEFAULT 0,
            UNIQUE (user_id, subject_id)
        );
        """)


# ------------------------------------------------------------- المستخدمون --

def upsert_user(user_id, full_name, username=None, role=None):
    with get_conn() as conn:
        row = conn.execute("SELECT user_id FROM Users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            conn.execute("UPDATE Users SET full_name=?, username=? WHERE user_id=?",
                         (full_name, username, user_id))
            if role:
                conn.execute("UPDATE Users SET role=? WHERE user_id=?", (role, user_id))
        else:
            conn.execute(
                "INSERT INTO Users (user_id, full_name, username, role) VALUES (?,?,?,?)",
                (user_id, full_name, username, role or "student"))


def get_user(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM Users WHERE user_id=?", (user_id,)).fetchone()


def get_role(user_id, admin_ids=()):
    if user_id in admin_ids:
        return "admin"
    u = get_user(user_id)
    return u["role"] if u else None


def set_role(user_id, role):
    with get_conn() as conn:
        conn.execute("UPDATE Users SET role=? WHERE user_id=?", (role, user_id))


def set_student_info(user_id, university_id, level=None):
    with get_conn() as conn:
        conn.execute("UPDATE Users SET university_id=?, level=? WHERE user_id=?",
                     (university_id, level, user_id))


def get_users_by_role(role):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM Users WHERE role=? ORDER BY full_name", (role,)).fetchall()


# --------------------------------------------------------------- المدرسون --

def add_professor(user_id, degree=None):
    with get_conn() as conn:
        conn.execute("UPDATE Users SET role='professor' WHERE user_id=?", (user_id,))
        conn.execute("INSERT OR IGNORE INTO Professors (user_id, degree) VALUES (?,?)",
                     (user_id, degree))


def remove_professor(user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM Professors WHERE user_id=?", (user_id,))
        conn.execute("UPDATE Users SET role='student' WHERE user_id=?", (user_id,))


def get_professor_by_user(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM Professors WHERE user_id=?", (user_id,)).fetchone()


def get_all_professors():
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.professor_id, p.user_id, u.full_name, u.username
            FROM Professors p JOIN Users u ON u.user_id = p.user_id
            ORDER BY u.full_name""").fetchall()


# --------------------------------------------------------------- المقررات --

def add_subject(name, code=None, level=None):
    with get_conn() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO Subjects (name, code, level) VALUES (?,?,?)",
                           (name, code, level))
        return cur.lastrowid


def get_all_subjects():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM Subjects ORDER BY name").fetchall()


def get_subject(subject_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM Subjects WHERE subject_id=?", (subject_id,)).fetchone()


def assign_subject_to_professor(professor_id, subject_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO Professor_Subjects (professor_id, subject_id) VALUES (?,?)",
                     (professor_id, subject_id))


def unassign_subject_from_professor(professor_id, subject_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM Professor_Subjects WHERE professor_id=? AND subject_id=?",
                     (professor_id, subject_id))


def get_professor_subjects(user_id):
    """مقررات المدرس (حسب Telegram user_id)."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT s.* FROM Subjects s
            JOIN Professor_Subjects ps ON ps.subject_id = s.subject_id
            JOIN Professors p ON p.professor_id = ps.professor_id
            WHERE p.user_id = ? ORDER BY s.name""", (user_id,)).fetchall()


# ----------------------------------------------------------------- الطلاب --

def enroll_student(user_id, subject_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO Student_Subjects (user_id, subject_id) VALUES (?,?)",
                     (user_id, subject_id))


def unenroll_student(user_id, subject_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM Student_Subjects WHERE user_id=? AND subject_id=?",
                     (user_id, subject_id))


def get_student_subjects(user_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT s.* FROM Subjects s
            JOIN Student_Subjects ss ON ss.subject_id = s.subject_id
            WHERE ss.user_id = ? ORDER BY s.name""", (user_id,)).fetchall()


def get_subject_students(subject_id):
    """جميع طلاب مقرر محدد (لإرسال الإشعارات المستهدفة)."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT u.* FROM Users u
            JOIN Student_Subjects ss ON ss.user_id = u.user_id
            WHERE ss.subject_id = ? AND u.role = 'student'""", (subject_id,)).fetchall()


# --------------------------------------------------------------- المسابقات --

def create_competition(title, subject_id, creator_id, comp_type, num_questions,
                       question_seconds, start_time, end_time, status="draft"):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO Competitions
            (title, subject_id, creator_id, comp_type, num_questions,
             question_seconds, start_time, end_time, status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (title, subject_id, creator_id, comp_type, num_questions,
             question_seconds, start_time, end_time, status))
        return cur.lastrowid


def get_competition(competition_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM Competitions WHERE competition_id=?",
                            (competition_id,)).fetchone()


def set_competition_status(competition_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE Competitions SET status=? WHERE competition_id=?",
                     (status, competition_id))


def get_competitions_by_creator(creator_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT c.*, s.name AS subject_name FROM Competitions c
            LEFT JOIN Subjects s ON s.subject_id = c.subject_id
            WHERE c.creator_id=? ORDER BY c.created_at DESC""", (creator_id,)).fetchall()


def get_competitions_pending_review():
    with get_conn() as conn:
        return conn.execute("""
            SELECT c.*, s.name AS subject_name, u.full_name AS creator_name
            FROM Competitions c
            LEFT JOIN Subjects s ON s.subject_id = c.subject_id
            JOIN Users u ON u.user_id = c.creator_id
            WHERE c.status='pending_review' ORDER BY c.created_at""").fetchall()


def get_active_competitions_for_student(user_id):
    """المسابقات النشطة لمقررات الطالب + المسابقات العامة."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT c.*, s.name AS subject_name FROM Competitions c
            LEFT JOIN Subjects s ON s.subject_id = c.subject_id
            WHERE c.status = 'active'
              AND (c.subject_id IS NULL
                   OR c.subject_id IN (SELECT subject_id FROM Student_Subjects WHERE user_id=?))
              AND c.competition_id NOT IN (SELECT competition_id FROM Results WHERE user_id=?)
            ORDER BY c.start_time""", (user_id, user_id)).fetchall()


def get_scheduled_competitions():
    """المسابقات المعتمدة/النشطة التي لها مواعيد (لإعادة الجدولة عند إقلاع البوت)."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM Competitions
            WHERE status IN ('approved','active')""").fetchall()


# ---------------------------------------------------------------- الأسئلة --

def add_question(competition_id, text, a, b, c, d, correct, status="pending"):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO Questions
            (competition_id, text, option_a, option_b, option_c, option_d, correct_option, status)
            VALUES (?,?,?,?,?,?,?,?)""",
            (competition_id, text, a, b, c, d, correct, status))
        return cur.lastrowid


def get_competition_questions(competition_id, approved_only=False):
    q = "SELECT * FROM Questions WHERE competition_id=?"
    if approved_only:
        q += " AND status='approved'"
    q += " ORDER BY question_id"
    with get_conn() as conn:
        return conn.execute(q, (competition_id,)).fetchall()


def count_questions(competition_id):
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM Questions WHERE competition_id=?",
                            (competition_id,)).fetchone()["n"]


def set_questions_status(competition_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE Questions SET status=? WHERE competition_id=?",
                     (status, competition_id))


# ---------------------------------------------------------------- الإجابات --

def save_answer(question_id, user_id, selected_option, is_correct):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO Answers (question_id, user_id, selected_option, is_correct)
            VALUES (?,?,?,?)""", (question_id, user_id, selected_option, int(is_correct)))


# ---------------------------------------------------------------- النتائج --

def save_result(competition_id, user_id, score, total, time_taken):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO Results (competition_id, user_id, score, total, time_taken)
            VALUES (?,?,?,?,?)""", (competition_id, user_id, score, total, time_taken))


def get_competition_results(competition_id, limit=None):
    q = """
        SELECT r.*, u.full_name, u.university_id FROM Results r
        JOIN Users u ON u.user_id = r.user_id
        WHERE r.competition_id=?
        ORDER BY r.score DESC, r.time_taken ASC"""
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return conn.execute(q, (competition_id,)).fetchall()


def get_results_by_subject(subject_id):
    """نتائج جميع مسابقات مقرر محدد (مفصولة حسب المقرر)."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.*, u.full_name, u.university_id, c.title AS competition_title
            FROM Results r
            JOIN Users u ON u.user_id = r.user_id
            JOIN Competitions c ON c.competition_id = r.competition_id
            WHERE c.subject_id=?
            ORDER BY c.competition_id DESC, r.score DESC""", (subject_id,)).fetchall()


def get_student_results(user_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.*, c.title, s.name AS subject_name FROM Results r
            JOIN Competitions c ON c.competition_id = r.competition_id
            LEFT JOIN Subjects s ON s.subject_id = c.subject_id
            WHERE r.user_id=? ORDER BY r.finished_at DESC""", (user_id,)).fetchall()


# ------------------------------------------------------------ لوحة الترتيب --

def add_leaderboard_points(user_id, subject_id, points):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO Leaderboard (user_id, subject_id, points) VALUES (?,?,?)
            ON CONFLICT (user_id, subject_id) DO UPDATE SET points = points + excluded.points""",
            (user_id, subject_id, points))
        # الترتيب العام (subject_id = NULL) — ON CONFLICT لا يعمل مع NULL في UNIQUE
        row = conn.execute(
            "SELECT id FROM Leaderboard WHERE user_id=? AND subject_id IS NULL",
            (user_id,)).fetchone()
        if row:
            conn.execute("UPDATE Leaderboard SET points = points + ? WHERE id=?",
                         (points, row["id"]))
        else:
            conn.execute("INSERT INTO Leaderboard (user_id, subject_id, points) VALUES (?, NULL, ?)",
                         (user_id, points))


def get_leaderboard(subject_id=None, limit=10):
    with get_conn() as conn:
        if subject_id is None:
            return conn.execute("""
                SELECT l.points, u.full_name, u.university_id FROM Leaderboard l
                JOIN Users u ON u.user_id = l.user_id
                WHERE l.subject_id IS NULL
                ORDER BY l.points DESC LIMIT ?""", (limit,)).fetchall()
        return conn.execute("""
            SELECT l.points, u.full_name, u.university_id FROM Leaderboard l
            JOIN Users u ON u.user_id = l.user_id
            WHERE l.subject_id = ?
            ORDER BY l.points DESC LIMIT ?""", (subject_id, limit)).fetchall()


# ---------------------------------------------------------------- التقارير --

def get_stats():
    with get_conn() as conn:
        stats = {}
        stats["students"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Users WHERE role='student'").fetchone()["n"]
        stats["professors"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Professors").fetchone()["n"]
        stats["committee"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Users WHERE role='committee'").fetchone()["n"]
        stats["subjects"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Subjects").fetchone()["n"]
        stats["competitions"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Competitions").fetchone()["n"]
        stats["active_competitions"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Competitions WHERE status='active'").fetchone()["n"]
        stats["results"] = conn.execute(
            "SELECT COUNT(*) AS n FROM Results").fetchone()["n"]
        return stats
