import os
import hashlib
import mimetypes
import secrets
from io import BytesIO
from datetime import datetime, timezone, timedelta
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
)
from werkzeug.security import check_password_hash
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ============================================================
# TIMEZONE
# ============================================================
# Users enter scheduled release times in India Standard Time (IST).
# Times are stored in UTC in the database for consistent server-side
# comparisons, then displayed back to users in IST.
IST = timezone(timedelta(hours=5, minutes=30), "IST")


def parse_scheduled_release_ist(value):
    """Convert a datetime-local value entered in IST into UTC ISO format."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    return dt.astimezone(timezone.utc).isoformat()


def format_ist(value):
    """Display a stored UTC/ISO datetime in IST."""
    if not value:
        return "Immediate"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except (ValueError, TypeError):
        return str(value)


def normalize_centre(value):
    """Normalize centre names so harmless case/spacing differences do not block access."""
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).casefold()


# ============================================================
# CONFIGURATION
# ============================================================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "question-papers")
PAPER_ENCRYPTION_KEY = os.getenv("PAPER_ENCRYPTION_KEY", "")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing in .env")

SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_PUBLISHABLE_KEY
if not SUPABASE_KEY:
    raise RuntimeError(
        "Set SUPABASE_SERVICE_ROLE_KEY (recommended) or SUPABASE_PUBLISHABLE_KEY in .env"
    )

if not PAPER_ENCRYPTION_KEY:
    raise RuntimeError("PAPER_ENCRYPTION_KEY is missing in .env")

try:
    encryption_key = bytes.fromhex(PAPER_ENCRYPTION_KEY)
except ValueError as exc:
    raise RuntimeError("PAPER_ENCRYPTION_KEY must be hexadecimal.") from exc

if len(encryption_key) != 32:
    raise RuntimeError("PAPER_ENCRYPTION_KEY must contain exactly 64 hexadecimal characters.")

ROLES = {"SETTER", "MODERATOR", "RELEASE_OFFICER", "EXAM_CENTRE", "ADMIN"}

# ============================================================
# SUPABASE HELPERS
# ============================================================
def supabase_headers(content_type=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def supabase_request(method, endpoint, params=None, json=None, data=None, headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    final_headers = supabase_headers()
    if headers:
        final_headers.update(headers)
    try:
        return requests.request(
            method=method,
            url=url,
            params=params,
            json=json,
            data=data,
            headers=final_headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        print("SUPABASE REQUEST ERROR:", exc)
        return None


def safe_json(response, default=None):
    if response is None:
        return default
    try:
        return response.json()
    except (ValueError, TypeError):
        return default

# ============================================================
# AUTHORIZATION
# ============================================================
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "error")
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                flash("You are not authorized to access this page.", "error")
                return redirect(url_for("dashboard"))
            return function(*args, **kwargs)
        return wrapper
    return decorator


def role_home(role):
    if role == "ADMIN":
        return "admin_dashboard"
    if role == "MODERATOR":
        return "moderator_dashboard"
    if role == "RELEASE_OFFICER":
        return "release_dashboard"
    return "dashboard"

# ============================================================
# AUDIT LOGGING
# ============================================================
def write_audit_log(action, paper_id=None, details=None):
    payload = {
        "username": session.get("username"),
        "action": action,
        "paper_id": paper_id,
        "details": details,
        "ip_address": request.remote_addr,
    }
    try:
        response = supabase_request(
            "POST",
            "audit_logs",
            json=payload,
            headers={"Prefer": "return=minimal"},
        )
        if response is None or response.status_code not in (200, 201, 204):
            print("AUDIT LOG ERROR:", getattr(response, "text", "no response"))
    except Exception as exc:
        print("AUDIT LOG EXCEPTION:", exc)

# ============================================================
# DATA ACCESS
# ============================================================
def get_question_papers():
    response = supabase_request(
        "GET",
        "question_papers",
        params={"select": "*", "order": "id.desc"},
    )
    if response is None or response.status_code != 200:
        print("QUESTION PAPERS ERROR:", getattr(response, "status_code", None), getattr(response, "text", ""))
        return None
    return safe_json(response, [])


def get_users():
    response = supabase_request(
        "GET",
        "users",
        params={"select": "id,username,role,examination_centre,active,created_at", "order": "id.asc"},
    )
    if response is None or response.status_code != 200:
        print("USERS ERROR:", getattr(response, "status_code", None), getattr(response, "text", ""))
        return None
    return safe_json(response, [])


def get_user(user_id):
    """Load the current user from Supabase so centre changes are reflected immediately."""
    response = supabase_request(
        "GET",
        "users",
        params={"select": "id,username,role,examination_centre,active", "id": f"eq.{user_id}", "limit": "1"},
    )
    if response is None or response.status_code != 200:
        print("CURRENT USER ERROR:", getattr(response, "status_code", None), getattr(response, "text", ""))
        return None
    rows = safe_json(response, [])
    return rows[0] if rows else None


def get_audit_logs():
    response = supabase_request(
        "GET",
        "audit_logs",
        params={"select": "*", "order": "id.desc"},
    )
    if response is None or response.status_code != 200:
        print("AUDIT LOG ERROR:", getattr(response, "status_code", None), getattr(response, "text", ""))
        return None
    return safe_json(response, [])


def get_paper(paper_id):
    response = supabase_request(
        "GET",
        "question_papers",
        params={"select": "*", "id": f"eq.{paper_id}", "limit": "1"},
    )
    if response is None or response.status_code != 200:
        return None, response
    rows = safe_json(response, [])
    return (rows[0], response) if rows else (None, response)

# ============================================================
# CRYPTOGRAPHY
# ============================================================
def encrypt_file(file_bytes):
    nonce = os.urandom(12)
    encrypted = AESGCM(encryption_key).encrypt(nonce, file_bytes, None)
    return nonce + encrypted


def decrypt_file(encrypted_data):
    if len(encrypted_data) < 13:
        raise ValueError("Encrypted file is invalid.")
    return AESGCM(encryption_key).decrypt(encrypted_data[:12], encrypted_data[12:], None)


def calculate_sha256(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()

# ============================================================
# STORAGE
# ============================================================
def upload_to_storage(storage_path, encrypted_data):
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}"
    headers = supabase_headers("application/octet-stream")
    headers["x-upsert"] = "false"
    try:
        return requests.post(url, headers=headers, data=encrypted_data, timeout=60)
    except requests.RequestException as exc:
        print("STORAGE UPLOAD ERROR:", exc)
        return None


def download_from_storage(storage_path):
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}"
    try:
        return requests.get(url, headers=supabase_headers(), timeout=60)
    except requests.RequestException as exc:
        print("STORAGE DOWNLOAD ERROR:", exc)
        return None

# ============================================================
# HOME / LOGIN / LOGOUT
# ============================================================
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for(role_home(session.get("role"))))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter username and password.", "error")
            return render_template("login.html")

        response = supabase_request(
            "GET",
            "users",
            params={"select": "*", "username": f"eq.{username}", "limit": "1"},
        )
        if response is None or response.status_code != 200:
            flash("Could not connect to the database.", "error")
            return render_template("login.html")

        users = safe_json(response, [])
        if not users:
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        user = users[0]
        if not user.get("active", True):
            flash("This account is inactive.", "error")
            return render_template("login.html")

        try:
            valid = check_password_hash(user.get("password_hash", ""), password)
        except Exception as exc:
            print("PASSWORD CHECK ERROR:", exc)
            valid = False

        if not valid:
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["examination_centre"] = user.get("examination_centre")
        write_audit_log("LOGIN", details="User logged in")
        return redirect(url_for(role_home(user["role"])))

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user_id" in session:
        write_audit_log("LOGOUT", details="User logged out")
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

# ============================================================
# COMMON DASHBOARD
# ============================================================
@app.route("/dashboard")
@login_required
def dashboard():
    role = session.get("role")

    # Always refresh the logged-in user's centre from the database.
    # This prevents an old Flask session from keeping examination_centre=None.
    current_user = get_user(session.get("user_id"))
    if current_user:
        session["username"] = current_user.get("username", session.get("username"))
        session["role"] = current_user.get("role", role)
        session["examination_centre"] = current_user.get("examination_centre")
        role = session.get("role")

    papers = get_question_papers() or []

    if role == "EXAM_CENTRE":
        centre = normalize_centre(session.get("examination_centre"))
        if not centre:
            papers = []
            flash("No examination centre is assigned to this account.", "error")
        else:
            # Exam centres see only RELEASED papers assigned to their centre.
            papers = [
                p for p in papers
                if p.get("status", "").upper() == "RELEASED"
                and normalize_centre(p.get("examination_centre")) == centre
            ]

    for paper in papers:
        paper["scheduled_release_display"] = format_ist(paper.get("scheduled_release"))
        paper["released_at_display"] = format_ist(paper.get("released_at"))

    counts = {
        "total": len(papers),
        "pending": sum(p.get("status") == "PENDING" for p in papers),
        "approved": sum(p.get("status") == "APPROVED" for p in papers),
        "released": sum(p.get("status") == "RELEASED" for p in papers),
        "rejected": sum(p.get("status") == "REJECTED" for p in papers),
    }
    return render_template("dashboard.html", papers=papers, counts=counts, role=role)

# ============================================================
# PHASE 1 — SETTER: ENCRYPTED UPLOAD
# ============================================================
@app.route("/upload", methods=["GET", "POST"])
@role_required("SETTER", "ADMIN")
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    uploaded_file = request.files.get("file")
    examination_centre = request.form.get("examination_centre", "").strip()
    scheduled_release = request.form.get("scheduled_release", "").strip()

    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a question paper.", "error")
        return redirect(url_for("upload"))
    if not examination_centre:
        flash("Enter the examination centre.", "error")
        return redirect(url_for("upload"))

    original_name = os.path.basename(uploaded_file.filename)
    file_bytes = uploaded_file.read()
    if not file_bytes:
        flash("Uploaded file is empty.", "error")
        return redirect(url_for("upload"))

    # datetime-local has no timezone. In this application, the user-entered
    # value is explicitly treated as India Standard Time (Asia/Kolkata),
    # then converted to UTC before it is stored in the database.
    if scheduled_release:
        try:
            scheduled_release = parse_scheduled_release_ist(scheduled_release)
        except ValueError:
            flash("Invalid scheduled release date/time.", "error")
            return redirect(url_for("upload"))

    sha256 = calculate_sha256(file_bytes)
    try:
        encrypted_data = encrypt_file(file_bytes)
    except Exception as exc:
        print("ENCRYPTION ERROR:", exc)
        flash("File encryption failed.", "error")
        return redirect(url_for("upload"))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    safe_username = "".join(c if c.isalnum() or c in "._-" else "_" for c in session["username"])
    storage_path = f"encrypted/{safe_username}/{timestamp}_{original_name}.enc"

    storage_response = upload_to_storage(storage_path, encrypted_data)
    if storage_response is None or storage_response.status_code not in (200, 201):
        print("UPLOAD ERROR:", getattr(storage_response, "status_code", None), getattr(storage_response, "text", ""))
        flash("Question paper upload failed.", "error")
        return redirect(url_for("upload"))

    paper_data = {
        "original_name": original_name,
        "storage_path": storage_path,
        "sha256": sha256,
        "created_by": session["user_id"],
        "scheduled_release": scheduled_release or None,
        "examination_centre": examination_centre,
        "status": "PENDING",
    }
    db_response = supabase_request(
        "POST",
        "question_papers",
        json=paper_data,
        headers={"Prefer": "return=representation"},
    )
    if db_response is None or db_response.status_code not in (200, 201):
        print("QUESTION PAPER DATABASE ERROR:", getattr(db_response, "status_code", None), getattr(db_response, "text", ""))
        flash("File uploaded but database record could not be created.", "error")
        return redirect(url_for("upload"))

    rows = safe_json(db_response, [])
    paper_id = rows[0].get("id") if rows else None
    write_audit_log("UPLOAD", paper_id=paper_id, details=f"Encrypted question paper uploaded: {original_name}")
    flash("Question paper encrypted and uploaded successfully. Status: PENDING.", "success")
    return redirect(url_for("dashboard"))

# ============================================================
# PHASE 2 — MODERATOR: APPROVE / REJECT
# ============================================================
@app.route("/moderator")
@role_required("MODERATOR", "ADMIN")
def moderator_dashboard():
    response = supabase_request(
        "GET",
        "question_papers",
        params={"select": "*", "status": "eq.PENDING", "order": "id.desc"},
    )
    if response is None or response.status_code != 200:
        pending_papers = []
        flash("Could not load pending question papers.", "error")
    else:
        pending_papers = safe_json(response, [])

    # Four-eyes: show papers, but mark those created by current user as unavailable.
    for paper in pending_papers:
        paper["can_approve"] = paper.get("created_by") != session.get("user_id")
    return render_template("moderator.html", papers=pending_papers)


@app.route("/moderator/approve/<int:paper_id>", methods=["POST"])
@role_required("MODERATOR", "ADMIN")
def approve_paper(paper_id):
    paper, response = get_paper(paper_id)
    if paper is None:
        flash("Question paper not found.", "error")
        return redirect(url_for("moderator_dashboard"))
    if paper.get("status") != "PENDING":
        flash("Only PENDING papers can be approved.", "error")
        return redirect(url_for("moderator_dashboard"))
    if paper.get("created_by") == session.get("user_id"):
        write_audit_log("BLOCKED_APPROVAL", paper_id=paper_id, details="Four-eyes rule blocked self-approval")
        flash("Four-eyes rule: you cannot approve a paper you created.", "error")
        return redirect(url_for("moderator_dashboard"))

    update_data = {
        "status": "APPROVED",
        "approved_by": session["user_id"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "rejection_reason": None,
    }
    result = supabase_request(
        "PATCH",
        "question_papers",
        params={"id": f"eq.{paper_id}", "status": "eq.PENDING"},
        json=update_data,
        headers={"Prefer": "return=representation"},
    )
    if result is None or result.status_code not in (200, 204):
        print("APPROVE ERROR:", getattr(result, "status_code", None), getattr(result, "text", ""))
        flash("Could not approve question paper.", "error")
        return redirect(url_for("moderator_dashboard"))

    write_audit_log("APPROVE", paper_id=paper_id, details="Question paper approved by moderator")
    flash("Question paper approved successfully.", "success")
    return redirect(url_for("moderator_dashboard"))


@app.route("/moderator/reject/<int:paper_id>", methods=["POST"])
@role_required("MODERATOR", "ADMIN")
def reject_paper(paper_id):
    paper, _ = get_paper(paper_id)
    if paper is None:
        flash("Question paper not found.", "error")
        return redirect(url_for("moderator_dashboard"))
    if paper.get("status") != "PENDING":
        flash("Only PENDING papers can be rejected.", "error")
        return redirect(url_for("moderator_dashboard"))

    reason = request.form.get("reason", "Rejected by moderator").strip() or "Rejected by moderator"
    result = supabase_request(
        "PATCH",
        "question_papers",
        params={"id": f"eq.{paper_id}", "status": "eq.PENDING"},
        json={"status": "REJECTED", "rejection_reason": reason, "approved_by": None, "approved_at": None},
        headers={"Prefer": "return=representation"},
    )
    if result is None or result.status_code not in (200, 204):
        print("REJECT ERROR:", getattr(result, "status_code", None), getattr(result, "text", ""))
        flash("Could not reject question paper.", "error")
        return redirect(url_for("moderator_dashboard"))

    write_audit_log("REJECT", paper_id=paper_id, details=reason)
    flash("Question paper rejected.", "success")
    return redirect(url_for("moderator_dashboard"))

# ============================================================
# PHASE 3 — RELEASE OFFICER: TIME-LOCKED RELEASE
# ============================================================
@app.route("/release")
@role_required("RELEASE_OFFICER", "ADMIN")
def release_dashboard():
    response = supabase_request(
        "GET",
        "question_papers",
        params={"select": "*", "status": "eq.APPROVED", "order": "id.desc"},
    )
    if response is None or response.status_code != 200:
        papers = []
        flash("Could not load approved papers.", "error")
    else:
        papers = safe_json(response, [])

    now = datetime.now(timezone.utc)
    for paper in papers:
        paper["release_eligible"] = True
        scheduled = paper.get("scheduled_release")
        if scheduled:
            try:
                release_time = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
                if release_time.tzinfo is None:
                    release_time = release_time.replace(tzinfo=timezone.utc)
                paper["release_eligible"] = now >= release_time
            except ValueError:
                paper["release_eligible"] = False
        paper["scheduled_release_display"] = format_ist(scheduled)
    return render_template("release.html", papers=papers)


@app.route("/release/<int:paper_id>", methods=["POST"])
@role_required("RELEASE_OFFICER", "ADMIN")
def release_paper(paper_id):
    paper, _ = get_paper(paper_id)
    if paper is None:
        flash("Question paper not found.", "error")
        return redirect(url_for("release_dashboard"))
    if paper.get("status") != "APPROVED":
        flash("Only APPROVED papers can be released.", "error")
        return redirect(url_for("release_dashboard"))
    if paper.get("approved_by") == session.get("user_id"):
        write_audit_log("BLOCKED_RELEASE", paper_id=paper_id, details="Approver attempted to release the same paper")
        flash("Four-eyes rule: the approving user cannot release the same paper.", "error")
        return redirect(url_for("release_dashboard"))

    scheduled = paper.get("scheduled_release")
    if scheduled:
        try:
            release_time = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
            if release_time.tzinfo is None:
                release_time = release_time.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < release_time:
                write_audit_log("BLOCKED_EARLY_RELEASE", paper_id=paper_id, details=f"Scheduled for {scheduled} (stored UTC)")
                flash(f"Release blocked. Scheduled release is {format_ist(scheduled)}.", "error")
                return redirect(url_for("release_dashboard"))
        except ValueError:
            flash("The scheduled release time is invalid.", "error")
            return redirect(url_for("release_dashboard"))

    result = supabase_request(
        "PATCH",
        "question_papers",
        params={"id": f"eq.{paper_id}", "status": "eq.APPROVED"},
        json={"status": "RELEASED", "released_at": datetime.now(timezone.utc).isoformat()},
        headers={"Prefer": "return=representation"},
    )
    if result is None or result.status_code not in (200, 204):
        print("RELEASE ERROR:", getattr(result, "status_code", None), getattr(result, "text", ""))
        flash("Could not release question paper.", "error")
        return redirect(url_for("release_dashboard"))

    released_rows = safe_json(result, []) if result.status_code == 200 else []
    if result.status_code == 200 and not released_rows:
        print("RELEASE ERROR: no APPROVED paper was updated for id", paper_id)
        flash("The paper was not released. It may have changed status already.", "error")
        return redirect(url_for("release_dashboard"))

    write_audit_log("RELEASE", paper_id=paper_id, details="Question paper released after approval and time-lock checks")
    flash("Question paper released successfully.", "success")
    return redirect(url_for("release_dashboard"))

# ============================================================
# PHASE 4 — CONTROLLED DECRYPTION
# ============================================================
@app.route("/download/<int:paper_id>")
@role_required("RELEASE_OFFICER", "EXAM_CENTRE", "ADMIN")
def download_paper(paper_id):
    paper, response = get_paper(paper_id)
    if paper is None:
        flash("Question paper not found.", "error")
        return redirect(url_for("dashboard"))

    if paper.get("status") != "RELEASED":
        write_audit_log("BLOCKED_DECRYPT", paper_id=paper_id, details="Attempted to decrypt a non-released paper")
        flash("Decryption is available only after the paper is RELEASED.", "error")
        return redirect(url_for("dashboard"))

    # Exam-centre users are restricted to their assigned examination centre.
    if session.get("role") == "EXAM_CENTRE":
        assigned_centre = normalize_centre(session.get("examination_centre"))
        paper_centre = normalize_centre(paper.get("examination_centre"))
        if not assigned_centre or assigned_centre != paper_centre:
            write_audit_log(
                "BLOCKED_CENTRE_ACCESS",
                paper_id=paper_id,
                details=f"Exam-centre access blocked. Assigned centre: {session.get('examination_centre') or 'NONE'}"
            )
            flash("You are not authorized to access papers for this examination centre.", "error")
            return redirect(url_for("dashboard"))

    storage_path = paper.get("storage_path")
    if not storage_path:
        flash("Storage path is missing.", "error")
        return redirect(url_for("dashboard"))

    storage_response = download_from_storage(storage_path)
    if storage_response is None or storage_response.status_code != 200:
        print("STORAGE DOWNLOAD ERROR:", getattr(storage_response, "status_code", None), getattr(storage_response, "text", ""))
        write_audit_log("DECRYPT_FAILURE", paper_id=paper_id, details="Encrypted object could not be retrieved")
        flash("Could not retrieve encrypted question paper.", "error")
        return redirect(url_for("dashboard"))

    try:
        decrypted_data = decrypt_file(storage_response.content)
    except Exception as exc:
        print("DECRYPTION ERROR:", exc)
        write_audit_log("DECRYPT_FAILURE", paper_id=paper_id, details="AES-256-GCM authentication/decryption failed")
        flash("Could not decrypt question paper.", "error")
        return redirect(url_for("dashboard"))

    expected_hash = paper.get("sha256")
    actual_hash = calculate_sha256(decrypted_data)
    if expected_hash and actual_hash.lower() != expected_hash.lower():
        write_audit_log("INTEGRITY_FAILURE", paper_id=paper_id, details="SHA-256 verification failed after decryption")
        flash("Security verification failed. The paper may have been modified.", "error")
        return redirect(url_for("dashboard"))

    write_audit_log("DOWNLOAD_DECRYPT", paper_id=paper_id, details=f"Decrypted and downloaded: {paper.get('original_name')}")
    original_name = paper.get("original_name", "question_paper")
    mime_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    return send_file(BytesIO(decrypted_data), mimetype=mime_type, as_attachment=True, download_name=original_name)

# ============================================================
# PHASE 5 — ADMIN: USERS + PAPERS + AUDIT
# ============================================================
@app.route("/admin")
@role_required("ADMIN")
def admin_dashboard():
    papers = get_question_papers() or []
    users = get_users() or []
    logs = get_audit_logs() or []
    counts = {
        "users": len(users),
        "papers": len(papers),
        "pending": sum(p.get("status") == "PENDING" for p in papers),
        "approved": sum(p.get("status") == "APPROVED" for p in papers),
        "released": sum(p.get("status") == "RELEASED" for p in papers),
        "rejected": sum(p.get("status") == "REJECTED" for p in papers),
        "logs": len(logs),
    }
    return render_template("admin.html", papers=papers, users=users, logs=logs, counts=counts)


@app.route("/audit")
@role_required("ADMIN")
def audit_dashboard():
    logs = get_audit_logs()
    if logs is None:
        logs = []
        flash("Could not load audit logs.", "error")
    return render_template("audit.html", logs=logs)

# ============================================================
# HEALTH / ERRORS
# ============================================================
@app.route("/health")
def health():
    response = supabase_request("GET", "users", params={"select": "id", "limit": "1"})
    if response is not None and response.status_code == 200:
        return {"status": "ok", "supabase": "connected"}
    return {"status": "error", "supabase": "not connected"}, 500


@app.errorhandler(413)
def file_too_large(error):
    flash("File is too large. Maximum size is 20 MB.", "error")
    return redirect(url_for("upload"))


@app.errorhandler(404)
def not_found(error):
    if "user_id" in session:
        return render_template("dashboard.html", papers=get_question_papers() or [], counts={}, role=session.get("role")), 404
    return redirect(url_for("login"))


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.exception("Unhandled application error")
    return render_template("error.html", message="An unexpected server error occurred."), 500

# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("SECURE QUESTION PAPER MANAGEMENT SYSTEM")
    print("=" * 60)
    print("SUPABASE URL:", SUPABASE_URL)
    print("SERVICE KEY LOADED:", bool(SUPABASE_SERVICE_ROLE_KEY))
    print("BUCKET:", SUPABASE_BUCKET)
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=True)
