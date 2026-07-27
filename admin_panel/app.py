# -*- coding: utf-8 -*-
"""
لوحة تحكم البوت — واجهة ويب (Flask) لإدارة إعدادات البوت وقاعدة بياناته.
================================================================
تسمح لمالك البوت بـ:
  • تعديل جميع إعدادات البوت (config.json) مع الاحتفاظ بالقيم الحالية كافتراضية
  • إدارة المقررات والمدرسين ولجنة المسابقات والطلاب والمسابقات
  • تشغيل/إيقاف/إعادة تشغيل البوت وتطبيق الإعدادات
  • عرض التقارير والإحصائيات

التشغيل:
    python admin_panel/app.py
ثم افتح المتصفح على:  http://127.0.0.1:5000
"""
import os
import sys
import io
import csv
import json
import time
import secrets
import subprocess
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, Response, abort)
from werkzeug.security import generate_password_hash, check_password_hash

# --- إتاحة استيراد حزمة البوت (database) من المجلد الأصل ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, PANEL_DIR)

from database import db                                    # noqa: E402
from config_io import (load_config, save_config,           # noqa: E402
                       build_config_from_form)
from telegram_api import get_me, send_message              # noqa: E402

try:
    import psutil
except ImportError:
    psutil = None

AUTH_PATH = os.path.join(PANEL_DIR, "panel_auth.json")
LOG_PATH = os.path.join(BASE_DIR, "bot_run.log")
BOT_SCRIPT = os.path.join(BASE_DIR, "bot.py")
DEFAULT_PYTHON = r"C:\ProgramData\anaconda3\pythonw.exe"

ROLE_LABELS = {
    "admin": "مشرف عام",
    "professor": "مدرّس",
    "committee": "لجنة المسابقات",
    "student": "طالب",
}
COMP_STATUS_LABELS = {
    "draft": "مسودة",
    "pending_review": "بانتظار المراجعة",
    "approved": "معتمدة (مجدولة)",
    "active": "نشطة",
    "closed": "مغلقة",
    "rejected": "مرفوضة",
}
COMP_TYPE_LABELS = {
    "weekly": "أسبوعية", "monthly": "شهرية",
    "challenge": "تحدي", "general": "عامة",
}
OPTION_LABELS = {"a": "أ", "b": "ب", "c": "ج", "d": "د"}
PER_PAGE = 25


def safe_int(value, default=1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def paginate(items, page, per_page=PER_PAGE):
    """تقسيم قائمة إلى صفحات؛ يُرجع (عناصر الصفحة، الصفحة، إجمالي الصفحات، الإجمالي)."""
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    return items[start:start + per_page], page, pages, total


def make_csv(headers, rows, filename):
    """بناء استجابة CSV بترميز UTF-8 مع BOM ليظهر العربي في Excel."""
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


def panel_creator_id():
    """معرّف منشئ للمسابقات المنشأة من اللوحة (أول مشرف، أو مستخدم نظام)."""
    cfg = load_config()
    admins = cfg.get("admin_ids") or []
    if admins:
        uid = admins[0]
        if not db.get_user(uid):
            db.upsert_user(uid, "المشرف (لوحة التحكم)", role="admin")
        return uid
    SYS_ID = 1
    if not db.get_user(SYS_ID):
        db.upsert_user(SYS_ID, "لوحة التحكم", role="admin")
    return SYS_ID


# ==================================================================
#  المصادقة وإعدادات اللوحة (panel_auth.json)
# ==================================================================

def load_auth():
    if os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_auth(data):
    with open(AUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_auth_defaults():
    """توليد مفتاح الجلسة ومسار بايثون عند أول تشغيل."""
    auth = load_auth()
    changed = False
    if "secret_key" not in auth:
        auth["secret_key"] = secrets.token_hex(32)
        changed = True
    if "python_path" not in auth:
        auth["python_path"] = DEFAULT_PYTHON
        changed = True
    if changed:
        save_auth(auth)
    return auth


_auth = ensure_auth_defaults()

app = Flask(__name__)
app.secret_key = _auth["secret_key"]
# تقوية ملف تعريف الجلسة
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# ---- حماية CSRF (رمز في الجلسة يُتحقَّق منه في كل POST) ----

@app.before_request
def csrf_protect():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    if request.method == "POST":
        expected = session.get("csrf_token")
        received = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not expected or received != expected:
            abort(400, "رمز الحماية (CSRF) غير صالح. أعد تحميل الصفحة وحاول مجدداً.")


@app.context_processor
def inject_csrf():
    return {"csrf_token": session.get("csrf_token", "")}


# ---- تحديد محاولات الدخول (منع تخمين كلمة المرور) ----
_login_attempts = {}          # ip -> [عدد المحاولات, وقت أول محاولة]
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 300      # 5 دقائق حظر بعد تجاوز المحاولات


def login_locked(ip):
    rec = _login_attempts.get(ip)
    if not rec:
        return 0
    count, first = rec
    if count >= MAX_LOGIN_ATTEMPTS:
        elapsed = time.time() - first
        if elapsed < LOGIN_LOCK_SECONDS:
            return int(LOGIN_LOCK_SECONDS - elapsed)
        _login_attempts.pop(ip, None)
    return 0


def register_login_failure(ip):
    rec = _login_attempts.get(ip)
    if not rec or (time.time() - rec[1]) > LOGIN_LOCK_SECONDS:
        _login_attempts[ip] = [1, time.time()]
    else:
        rec[0] += 1


def password_is_set():
    return bool(load_auth().get("password_hash"))


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not password_is_set():
            return redirect(url_for("setup"))
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ==================================================================
#  التحكم بعملية البوت (تشغيل/إيقاف/إعادة تشغيل)
# ==================================================================

def bot_pid():
    """إرجاع PID لعملية البوت إن كانت تعمل، وإلا None."""
    if psutil is None:
        return None
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if any("bot.py" in str(a) for a in cmdline):
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None


def start_bot():
    auth = load_auth()
    python_path = auth.get("python_path", DEFAULT_PYTHON)
    if bot_pid():
        return False, "البوت يعمل بالفعل."
    if not os.path.exists(python_path):
        return False, f"مسار بايثون غير موجود: {python_path}"
    if not os.path.exists(BOT_SCRIPT):
        return False, "ملف bot.py غير موجود."
    try:
        logf = open(LOG_PATH, "ab")
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        subprocess.Popen([python_path, BOT_SCRIPT], cwd=BASE_DIR,
                         stdout=logf, stderr=logf, env=env, creationflags=flags)
        return True, "تم تشغيل البوت."
    except Exception as e:
        return False, f"تعذر التشغيل: {e}"


def stop_bot():
    pid = bot_pid()
    if not pid:
        return False, "البوت متوقف بالفعل."
    if psutil is None:
        return False, "psutil غير مثبتة — لا يمكن الإيقاف تلقائياً."
    try:
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(timeout=8)
        except psutil.TimeoutExpired:
            p.kill()
        return True, "تم إيقاف البوت."
    except Exception as e:
        return False, f"تعذر الإيقاف: {e}"


def read_log(lines=40):
    if not os.path.exists(LOG_PATH):
        return "لا يوجد سجل بعد. شغّل البوت من هذه اللوحة ليظهر سجله هنا."
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:]) or "(السجل فارغ)"
    except OSError as e:
        return f"تعذر قراءة السجل: {e}"


# ==================================================================
#  المصادقة: الإعداد الأولي / الدخول / الخروج
# ==================================================================

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if password_is_set():
        return redirect(url_for("login"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        pw2 = request.form.get("password2", "")
        if len(pw) < 6:
            flash("كلمة المرور يجب ألا تقل عن 6 أحرف.", "error")
        elif pw != pw2:
            flash("كلمتا المرور غير متطابقتين.", "error")
        else:
            auth = load_auth()
            auth["password_hash"] = generate_password_hash(pw)
            save_auth(auth)
            session["logged_in"] = True
            flash("تم إنشاء كلمة المرور بنجاح. مرحباً بك!", "success")
            return redirect(url_for("dashboard"))
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not password_is_set():
        return redirect(url_for("setup"))
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        locked = login_locked(ip)
        if locked:
            flash(f"محاولات كثيرة خاطئة. حاول بعد {locked // 60 + 1} دقيقة.", "error")
            return render_template("login.html")
        pw = request.form.get("password", "")
        if check_password_hash(load_auth().get("password_hash", ""), pw):
            _login_attempts.pop(ip, None)
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        register_login_failure(ip)
        flash("كلمة المرور غير صحيحة.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج.", "success")
    return redirect(url_for("login"))


# ==================================================================
#  لوحة التحكم الرئيسية + التحكم بالبوت
# ==================================================================

@app.route("/")
@login_required
def dashboard():
    cfg = load_config()
    stats = db.get_stats()
    running = bot_pid() is not None
    token_ok = bool(cfg.get("bot_token")) and not cfg["bot_token"].startswith("PUT_")
    admins_ok = bool(cfg.get("admin_ids")) and cfg["admin_ids"] != [123456789] \
        or bool(cfg.get("admin_usernames"))
    # بيانات الرسوم البيانية
    participation = db.get_participation_by_day(14)
    subj_perf = db.get_subject_performance()
    top_students = db.get_top_active_students(8)
    max_part = max([r["n"] for r in participation], default=1) or 1
    max_active = max([r["participations"] for r in top_students], default=1) or 1
    return render_template("dashboard.html",
                           stats=stats, cfg=cfg, running=running,
                           token_ok=token_ok, admins_ok=admins_ok,
                           psutil_ok=psutil is not None,
                           log=read_log(), auth=load_auth(),
                           participation=participation, subj_perf=subj_perf,
                           top_students=top_students,
                           max_part=max_part, max_active=max_active)


@app.route("/api/status")
@login_required
def api_status():
    """حالة البوت وآخر السجل — للتحديث التلقائي (AJAX)."""
    return jsonify(running=bot_pid() is not None, log=read_log(),
                   psutil_ok=psutil is not None)


@app.route("/bot/<action>", methods=["POST"])
@login_required
def bot_control(action):
    if action == "start":
        ok, msg = start_bot()
    elif action == "stop":
        ok, msg = stop_bot()
    elif action == "restart":
        stop_bot()
        import time
        time.sleep(2)
        ok, msg = start_bot()
        msg = "تمت إعادة التشغيل." if ok else msg
    else:
        ok, msg = False, "إجراء غير معروف."
    flash(msg, "success" if ok else "error")
    return redirect(url_for("dashboard"))


# ==================================================================
#  إعدادات البوت (config.json)
# ==================================================================

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    cfg = load_config()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "bot_config":
            new_cfg = build_config_from_form(request.form, cfg)
            db_changed = new_cfg.get("database_path") != cfg.get("database_path")
            save_config(new_cfg)
            flash("تم حفظ إعدادات البوت. أعد تشغيل البوت لتطبيق التغييرات.", "success")
            if db_changed:
                flash("⚠️ غيّرت مسار قاعدة البيانات — يجب إعادة تشغيل لوحة التحكم "
                      "نفسها (وليس البوت فقط) حتى تعمل اللوحة على القاعدة الجديدة.",
                      "error")
            return redirect(url_for("settings"))
        if form_type == "panel_settings":
            auth = load_auth()
            new_python = request.form.get("python_path", "").strip()
            if new_python:
                auth["python_path"] = new_python
            new_pw = request.form.get("new_password", "")
            if new_pw:
                if len(new_pw) < 6:
                    flash("كلمة المرور الجديدة قصيرة (6 أحرف على الأقل).", "error")
                    return redirect(url_for("settings"))
                auth["password_hash"] = generate_password_hash(new_pw)
                flash("تم تحديث كلمة مرور اللوحة.", "success")
            save_auth(auth)
            flash("تم حفظ إعدادات اللوحة.", "success")
            return redirect(url_for("settings"))
    return render_template("settings.html", cfg=cfg, auth=load_auth())


@app.route("/api/verify_token", methods=["POST"])
@login_required
def verify_token():
    """التحقق من صحة توكن البوت عبر getMe (يُستخدم من زر التحقق في الإعدادات)."""
    token = (request.form.get("token", "") or "").strip()
    if not token:
        token = load_config().get("bot_token", "")
    if not token or token.startswith("PUT_"):
        return jsonify(ok=False, error="لا يوجد توكن للتحقق منه.")
    res = get_me(token)
    if res.get("ok"):
        info = res["result"]
        return jsonify(ok=True, id=info.get("id"),
                       name=info.get("first_name", ""),
                       username=info.get("username", ""))
    return jsonify(ok=False, error=res.get("description", "توكن غير صالح."))


# ==================================================================
#  إدارة المقررات
# ==================================================================

@app.route("/subjects")
@login_required
def subjects():
    return render_template("subjects.html", subjects=db.get_all_subjects())


@app.route("/subjects/add", methods=["POST"])
@login_required
def subjects_add():
    name = request.form.get("name", "").strip()
    if name:
        db.add_subject(name,
                       request.form.get("code", "").strip() or None,
                       request.form.get("level", "").strip() or None)
        flash("تمت إضافة المقرر.", "success")
    else:
        flash("اسم المقرر مطلوب.", "error")
    return redirect(url_for("subjects"))


@app.route("/subjects/edit/<int:sid>", methods=["POST"])
@login_required
def subjects_edit(sid):
    name = request.form.get("name", "").strip()
    if name:
        db.update_subject(sid, name,
                          request.form.get("code", "").strip() or None,
                          request.form.get("level", "").strip() or None)
        flash("تم تحديث المقرر.", "success")
    return redirect(url_for("subjects"))


@app.route("/subjects/delete/<int:sid>", methods=["POST"])
@login_required
def subjects_delete(sid):
    db.delete_subject(sid)
    flash("تم حذف المقرر.", "success")
    return redirect(url_for("subjects"))


@app.route("/subjects/results/<int:sid>/export")
@login_required
def subjects_results_export(sid):
    rows_data = db.get_results_by_subject(sid)
    headers = ["المسابقة", "الاسم", "الرقم الجامعي", "الدرجة", "من", "الزمن (ث)"]
    rows = [[r["competition_title"], r["full_name"], r["university_id"] or "",
             r["score"], r["total"], r["time_taken"]] for r in rows_data]
    return make_csv(headers, rows, f"subject_{sid}_results.csv")


def _read_uploaded_csv(field="file"):
    """قراءة ملف CSV مرفوع وإرجاع صفوفه (يتعامل مع BOM ونهايات الأسطر)."""
    file = request.files.get(field)
    if not file or not file.filename:
        return None
    content = file.read().decode("utf-8-sig", errors="replace")
    return list(csv.reader(io.StringIO(content)))


@app.route("/subjects/import", methods=["POST"])
@login_required
def subjects_import():
    rows = _read_uploaded_csv()
    if rows is None:
        flash("لم يُختَر ملف.", "error")
        return redirect(url_for("subjects"))
    added, skipped = 0, 0
    for row in rows:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        if name.lower() in ("name", "الاسم", "المقرر", "اسم المقرر"):
            continue  # تخطي صف العناوين
        code = row[1].strip() if len(row) > 1 and row[1].strip() else None
        level = row[2].strip() if len(row) > 2 and row[2].strip() else None
        try:
            db.add_subject(name, code, level)
            added += 1
        except Exception:
            skipped += 1
    flash(f"تم استيراد {added} مقرر." + (f" (تخطّي {skipped})" if skipped else ""),
          "success")
    return redirect(url_for("subjects"))


@app.route("/students/import", methods=["POST"])
@login_required
def students_import():
    rows = _read_uploaded_csv()
    if rows is None:
        flash("لم يُختَر ملف.", "error")
        return redirect(url_for("students"))
    added, skipped = 0, 0
    for row in rows:
        if not row or not row[0].strip():
            continue
        first = row[0].strip()
        if first.lower() in ("user_id", "id", "المعرف", "معرف"):
            continue  # صف العناوين
        try:
            uid = int(first)
        except ValueError:
            skipped += 1
            continue
        name = row[1].strip() if len(row) > 1 and row[1].strip() else f"طالب {uid}"
        univ = row[2].strip() if len(row) > 2 and row[2].strip() else None
        db.upsert_user(uid, name, role="student")
        if univ:
            db.set_student_info(uid, univ)
        added += 1
    flash(f"تم استيراد {added} طالب." + (f" (تخطّي {skipped})" if skipped else ""),
          "success")
    return redirect(url_for("students"))


# ==================================================================
#  إدارة المدرسين
# ==================================================================

@app.route("/professors")
@login_required
def professors():
    profs = db.get_all_professors()
    data = []
    for p in profs:
        data.append({
            "user_id": p["user_id"],
            "full_name": p["full_name"],
            "username": p["username"],
            "subjects": db.get_professor_subjects(p["user_id"]),
        })
    return render_template("professors.html", professors=data,
                           all_subjects=db.get_all_subjects())


@app.route("/professors/add", methods=["POST"])
@login_required
def professors_add():
    try:
        uid = int(request.form.get("user_id", "").strip())
    except ValueError:
        flash("معرف تيليجرام يجب أن يكون رقماً.", "error")
        return redirect(url_for("professors"))
    name = request.form.get("full_name", "").strip()
    if not name:
        flash("اسم المدرس مطلوب.", "error")
        return redirect(url_for("professors"))
    db.upsert_user(uid, name, request.form.get("username", "").strip() or None,
                   role="professor")
    db.add_professor(uid)
    flash("تمت إضافة المدرس.", "success")
    return redirect(url_for("professors"))


@app.route("/professors/delete/<int:uid>", methods=["POST"])
@login_required
def professors_delete(uid):
    db.remove_professor(uid)
    flash("تمت إزالة المدرس.", "success")
    return redirect(url_for("professors"))


@app.route("/professors/subjects/<int:uid>", methods=["POST"])
@login_required
def professors_set_subjects(uid):
    selected = [int(x) for x in request.form.getlist("subject_ids")]
    db.set_professor_subjects(uid, selected)
    flash("تم تحديث مقررات المدرس.", "success")
    return redirect(url_for("professors"))


# ==================================================================
#  إدارة لجنة المسابقات
# ==================================================================

@app.route("/committee")
@login_required
def committee():
    return render_template("committee.html",
                           members=db.get_users_by_role("committee"))


@app.route("/committee/add", methods=["POST"])
@login_required
def committee_add():
    try:
        uid = int(request.form.get("user_id", "").strip())
    except ValueError:
        flash("معرف تيليجرام يجب أن يكون رقماً.", "error")
        return redirect(url_for("committee"))
    name = request.form.get("full_name", "").strip()
    if not name:
        flash("اسم العضو مطلوب.", "error")
        return redirect(url_for("committee"))
    db.add_or_update_committee(uid, name,
                               request.form.get("username", "").strip() or None)
    flash("تمت إضافة عضو اللجنة.", "success")
    return redirect(url_for("committee"))


@app.route("/committee/delete/<int:uid>", methods=["POST"])
@login_required
def committee_delete(uid):
    db.set_role(uid, "student")
    flash("تمت إزالة العضو من اللجنة.", "success")
    return redirect(url_for("committee"))


# ==================================================================
#  إدارة الطلاب
# ==================================================================

@app.route("/students")
@login_required
def students():
    q = (request.args.get("q", "") or "").strip()
    page = safe_int(request.args.get("page"), 1)
    all_students = db.get_users_by_role("student")
    if q:
        ql = q.lower()
        all_students = [s for s in all_students
                        if ql in (s["full_name"] or "").lower()
                        or ql in (s["university_id"] or "")]
    items, page, pages, total = paginate(all_students, page)
    enrolled_map = {s["user_id"]: db.get_student_subject_ids(s["user_id"])
                    for s in items}
    return render_template("students.html", students=items, role_labels=ROLE_LABELS,
                           q=q, page=page, pages=pages, total=total,
                           all_subjects=db.get_all_subjects(),
                           enrolled_map=enrolled_map)


@app.route("/students/role/<int:uid>", methods=["POST"])
@login_required
def students_role(uid):
    role = request.form.get("role")
    if role in ROLE_LABELS:
        db.set_role(uid, role)
        if role == "professor":
            db.add_professor(uid)
        flash("تم تغيير دور المستخدم.", "success")
    return redirect(url_for("students"))


@app.route("/students/delete/<int:uid>", methods=["POST"])
@login_required
def students_delete(uid):
    db.delete_user(uid)
    flash("تم حذف المستخدم.", "success")
    return redirect(url_for("students"))


@app.route("/students/subjects/<int:uid>", methods=["POST"])
@login_required
def students_set_subjects(uid):
    selected = [int(x) for x in request.form.getlist("subject_ids")]
    db.set_student_subjects(uid, selected)
    flash("تم تحديث مقررات الطالب.", "success")
    return redirect(url_for("students"))


# ==================================================================
#  إدارة المسابقات
# ==================================================================

@app.route("/competitions")
@login_required
def competitions():
    q = (request.args.get("q", "") or "").strip()
    page = safe_int(request.args.get("page"), 1)
    comps = db.get_all_competitions()
    if q:
        ql = q.lower()
        comps = [c for c in comps
                 if ql in (c["title"] or "").lower()
                 or ql in (c["subject_name"] or "").lower()]
    items, page, pages, total = paginate(comps, page)
    data = []
    for c in items:
        d = dict(c)
        d["questions_count"] = db.count_questions(c["competition_id"])
        d["results_count"] = len(db.get_competition_results(c["competition_id"]))
        data.append(d)
    return render_template("competitions.html", competitions=data,
                           status_labels=COMP_STATUS_LABELS,
                           type_labels=COMP_TYPE_LABELS,
                           q=q, page=page, pages=pages, total=total)


@app.route("/competitions/new", methods=["GET", "POST"])
@login_required
def competitions_new():
    if request.method == "POST":
        f = request.form
        subject_id = f.get("subject_id") or None
        subject_id = int(subject_id) if subject_id else None
        cid = db.create_competition(
            title=f.get("title", "").strip() or "مسابقة بلا عنوان",
            subject_id=subject_id,
            creator_id=panel_creator_id(),
            comp_type=f.get("comp_type", "weekly"),
            num_questions=safe_int(f.get("num_questions"), 5),
            question_seconds=safe_int(f.get("question_seconds"), 60),
            start_time=f.get("start_time", "").strip(),
            end_time=f.get("end_time", "").strip(),
            status=f.get("status", "draft"))
        flash("تم إنشاء المسابقة. أضف الأسئلة الآن.", "success")
        return redirect(url_for("competitions_edit", cid=cid))
    return render_template("competition_form.html", mode="new", comp=None,
                           questions=[], subjects=db.get_all_subjects(),
                           type_labels=COMP_TYPE_LABELS,
                           status_labels=COMP_STATUS_LABELS,
                           option_labels=OPTION_LABELS)


@app.route("/competitions/edit/<int:cid>", methods=["GET", "POST"])
@login_required
def competitions_edit(cid):
    comp = db.get_competition(cid)
    if not comp:
        flash("المسابقة غير موجودة.", "error")
        return redirect(url_for("competitions"))
    if request.method == "POST":
        f = request.form
        subject_id = f.get("subject_id") or None
        subject_id = int(subject_id) if subject_id else None
        db.update_competition(
            cid, f.get("title", "").strip() or comp["title"], subject_id,
            f.get("comp_type", comp["comp_type"]),
            safe_int(f.get("num_questions"), comp["num_questions"]),
            safe_int(f.get("question_seconds"), comp["question_seconds"]),
            f.get("start_time", "").strip(), f.get("end_time", "").strip())
        flash("تم حفظ بيانات المسابقة.", "success")
        return redirect(url_for("competitions_edit", cid=cid))
    return render_template("competition_form.html", mode="edit", comp=comp,
                           questions=db.get_competition_questions(cid),
                           subjects=db.get_all_subjects(),
                           type_labels=COMP_TYPE_LABELS,
                           status_labels=COMP_STATUS_LABELS,
                           option_labels=OPTION_LABELS)


@app.route("/competitions/<int:cid>/questions/add", methods=["POST"])
@login_required
def questions_add(cid):
    f = request.form
    text = f.get("text", "").strip()
    if text:
        db.add_question(cid, text,
                        f.get("option_a", "").strip(), f.get("option_b", "").strip(),
                        f.get("option_c", "").strip(), f.get("option_d", "").strip(),
                        f.get("correct_option", "a"), status="approved")
        flash("تمت إضافة السؤال.", "success")
    else:
        flash("نص السؤال مطلوب.", "error")
    return redirect(url_for("competitions_edit", cid=cid))


@app.route("/questions/<int:qid>/edit", methods=["POST"])
@login_required
def questions_edit(qid):
    q = db.get_question(qid)
    if not q:
        flash("السؤال غير موجود.", "error")
        return redirect(url_for("competitions"))
    f = request.form
    db.update_question(qid, f.get("text", "").strip() or q["text"],
                       f.get("option_a", "").strip(), f.get("option_b", "").strip(),
                       f.get("option_c", "").strip(), f.get("option_d", "").strip(),
                       f.get("correct_option", q["correct_option"]))
    flash("تم تحديث السؤال.", "success")
    return redirect(url_for("competitions_edit", cid=q["competition_id"]))


@app.route("/questions/<int:qid>/delete", methods=["POST"])
@login_required
def questions_delete(qid):
    q = db.get_question(qid)
    if q:
        db.delete_question(qid)
        flash("تم حذف السؤال.", "success")
        return redirect(url_for("competitions_edit", cid=q["competition_id"]))
    return redirect(url_for("competitions"))


@app.route("/competitions/results/<int:cid>/export")
@login_required
def competitions_results_export(cid):
    comp = db.get_competition(cid)
    results = db.get_competition_results(cid)
    headers = ["#", "الاسم", "الرقم الجامعي", "الدرجة", "من", "الزمن (ث)"]
    rows = [[i, r["full_name"], r["university_id"] or "", r["score"],
             r["total"], r["time_taken"]]
            for i, r in enumerate(results, start=1)]
    return make_csv(headers, rows, f"competition_{cid}_results.csv")


@app.route("/competitions/status/<int:cid>", methods=["POST"])
@login_required
def competitions_status(cid):
    status = request.form.get("status")
    if status in COMP_STATUS_LABELS:
        db.set_competition_status(cid, status)
        flash("تم تحديث حالة المسابقة.", "success")
    return redirect(url_for("competitions"))


@app.route("/competitions/delete/<int:cid>", methods=["POST"])
@login_required
def competitions_delete(cid):
    db.delete_competition(cid)
    flash("تم حذف المسابقة.", "success")
    return redirect(url_for("competitions"))


@app.route("/competitions/results/<int:cid>")
@login_required
def competitions_results(cid):
    comp = db.get_competition(cid)
    results = db.get_competition_results(cid)
    return render_template("results.html", comp=comp, results=results,
                           status_labels=COMP_STATUS_LABELS)


# ==================================================================
#  إرسال إشعار جماعي (Broadcast)
# ==================================================================

@app.route("/broadcast", methods=["GET", "POST"])
@login_required
def broadcast():
    cfg = load_config()
    token = cfg.get("bot_token", "")
    token_ok = bool(token) and not token.startswith("PUT_")
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        target = request.form.get("target", "all")
        if not token_ok:
            flash("توكن البوت غير مضبوط — لا يمكن الإرسال.", "error")
        elif not message:
            flash("نص الإشعار مطلوب.", "error")
        else:
            if target == "all":
                recipients = db.get_users_by_role("student")
                target_name = "جميع الطلاب"
            else:
                sid = int(target)
                recipients = db.get_subject_students(sid)
                subj = db.get_subject(sid)
                target_name = subj["name"] if subj else "مقرر"
            header = f"📢 إشعار\n\n{message}"
            sent, failed = 0, 0
            for r in recipients:
                res = send_message(token, r["user_id"], header)
                if res.get("ok"):
                    sent += 1
                else:
                    failed += 1
            flash(f"تم الإرسال إلى {sent} ({target_name})."
                  + (f" تعذّر الوصول إلى {failed}." if failed else ""),
                  "success" if sent else "error")
        return redirect(url_for("broadcast"))
    return render_template("broadcast.html", subjects=db.get_all_subjects(),
                           token_ok=token_ok)


# ==================================================================
#  صفحة التعليمات
# ==================================================================

@app.route("/instructions")
@login_required
def instructions():
    return render_template("instructions.html")


# ==================================================================

@app.context_processor
def inject_globals():
    return {"bot_running": bot_pid() is not None,
            "role_labels": ROLE_LABELS}


if __name__ == "__main__":
    db.init_db()
    print("=" * 55)
    print(" لوحة تحكم البوت تعمل الآن")
    print(" افتح المتصفح على:  http://127.0.0.1:5000")
    print("=" * 55)
    # 127.0.0.1 فقط: اللوحة غير متاحة على الشبكة لحماية التوكن
    try:
        from waitress import serve   # خادم إنتاجي أكثر استقراراً
        print(" (يعمل عبر خادم waitress)")
        serve(app, host="127.0.0.1", port=5000, threads=8)
    except ImportError:
        print(" (waitress غير مثبتة — استخدام خادم Flask التطويري)")
        app.run(host="127.0.0.1", port=5000, debug=False)
