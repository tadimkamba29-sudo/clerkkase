"""
Flask API for ClerKase — main application entry point.

Changes from Kimi original
--------------------------
1. Auth routes added  : POST /api/auth/register
                        POST /api/auth/login
                        POST /api/auth/refresh
                        GET  /api/auth/me
2. @login_required    : create_case, delete_case
3. @optional_auth     : list_cases (scopes to user when token present)
4. Dict access        : case_state is now a plain dict (from our new
                        StateManager._to_proxy), so all .attr access
                        has been changed to ["key"] access throughout.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

from flask import Flask, g, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ── App components — each import guarded so a missing package never prevents
# the Flask app from starting. /api/health will report what failed.
# ─────────────────────────────────────────────────────────────────────────────

_import_errors: dict = {}

def _safe_import(name, stmt):
    try:
        ns = {}
        exec(stmt, ns)
        return ns
    except Exception as e:
        _import_errors[name] = str(e)
        print(f"[ClerKase] IMPORT ERROR ({name}): {e}", flush=True)
        return {}

_db = _safe_import("database",
    "from database import init_db, SessionLocal, User, SectionStatus")
init_db       = _db.get("init_db")
SessionLocal  = _db.get("SessionLocal")
User          = _db.get("User")
SectionStatus = _db.get("SectionStatus")

_auth = _safe_import("auth",
    "from auth import (hash_password, verify_password, validate_password_strength,"
    " create_access_token, create_refresh_token, decode_token,"
    " extract_bearer_token, login_required, optional_auth)")
hash_password             = _auth.get("hash_password")
verify_password           = _auth.get("verify_password")
validate_password_strength = _auth.get("validate_password_strength")
create_access_token       = _auth.get("create_access_token")
create_refresh_token      = _auth.get("create_refresh_token")
decode_token              = _auth.get("decode_token")
extract_bearer_token      = _auth.get("extract_bearer_token")
login_required            = _auth.get("login_required",
                                lambda f: f)   # passthrough fallback
optional_auth             = _auth.get("optional_auth",
                                lambda f: f)   # passthrough fallback

_sm  = _safe_import("state_manager",   "from state_manager import get_state_manager")
_ip  = _safe_import("input_parser",    "from input_parser import get_input_parser")
_ce  = _safe_import("clarification_engine", "from clarification_engine import get_clarification_engine")
_dc  = _safe_import("document_compiler",    "from document_compiler import get_document_compiler")

get_state_manager        = _sm.get("get_state_manager")
get_input_parser         = _ip.get("get_input_parser")
get_clarification_engine = _ce.get("get_clarification_engine")
get_document_compiler    = _dc.get("get_document_compiler")

# ── Flask setup ───────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
    }
})

# ── Initialise singletons ─────────────────────────────────────────────────────
# Each wrapped so a single failure (e.g. DB unreachable) doesn't kill every
# route — /api/health and /api/rotations stay up even if the DB is down.

_init_errors: dict = {}

try:
    state_manager = get_state_manager()
except Exception as _e:
    state_manager = None  # type: ignore[assignment]
    _init_errors["state_manager"] = str(_e)
    print(f"[ClerKase] ERROR: state_manager failed to initialise: {_e}", flush=True)

try:
    input_parser = get_input_parser()
except Exception as _e:
    input_parser = None  # type: ignore[assignment]
    _init_errors["input_parser"] = str(_e)
    print(f"[ClerKase] ERROR: input_parser failed to initialise: {_e}", flush=True)

try:
    clarification_engine = get_clarification_engine(use_ai=True)
except Exception as _e:
    clarification_engine = None  # type: ignore[assignment]
    _init_errors["clarification_engine"] = str(_e)
    print(f"[ClerKase] ERROR: clarification_engine failed to initialise: {_e}", flush=True)

try:
    document_compiler = get_document_compiler("/tmp/exports")
except Exception as _e:
    document_compiler = None  # type: ignore[assignment]
    _init_errors["document_compiler"] = str(_e)
    print(f"[ClerKase] ERROR: document_compiler failed to initialise: {_e}", flush=True)


def _require(component, name: str):
    """Return component or abort with 503 if it failed to initialise."""
    if component is None:
        from flask import abort
        abort(503, description=f"{name} unavailable: {_init_errors.get(name, 'init error')}")
    return component


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request", "message": str(error)}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found", "message": str(error)}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error", "message": str(error)}), 500


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    all_errors = {**_import_errors, **_init_errors}
    status = "healthy" if not all_errors else "degraded"
    return jsonify({
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "errors": all_errors if all_errors else None,
    })


@app.route("/api/status", methods=["GET"])
def system_status():
    def _comp(c): return "active" if c is not None else "unavailable"
    ai_status = clarification_engine.get_ai_status() if clarification_engine else "unavailable"
    rotations = state_manager.get_available_rotations() if state_manager else []
    return jsonify({
        "status": "operational" if not _init_errors else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "state_manager": _comp(state_manager),
            "input_parser": _comp(input_parser),
            "clarification_engine": _comp(clarification_engine),
            "ai_clarifier": ai_status,
            "document_compiler": _comp(document_compiler),
        },
        "available_rotations": rotations,
        "init_errors": {**_import_errors, **_init_errors} or None,
    })


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route("/api/auth/register", methods=["POST"])
def register():
    """Register a new student account."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip() or None
    institution = (data.get("institution") or "").strip() or None

    # Basic field validation
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    if not username or len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    # Password strength
    ok, reason = validate_password_strength(password)
    if not ok:
        return jsonify({"error": reason}), 400

    db = SessionLocal()
    try:
        # Uniqueness checks
        if db.query(User).filter(User.email == email).first():
            return jsonify({"error": "An account with this email already exists"}), 409
        if db.query(User).filter(User.username == username).first():
            return jsonify({"error": "Username is already taken"}), 409

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            institution=institution,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        access_token = create_access_token(user.id, user.email, user.username)
        refresh_token = create_refresh_token(user.id)

        return jsonify({
            "message": "Account created successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_dict(),
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500
    finally:
        db.close()


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Log in with email + password, receive JWT tokens."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()

        # Generic message — do not reveal whether email exists
        if not user or not verify_password(password, user.hashed_password):
            return jsonify({"error": "Invalid email or password"}), 401

        if not user.is_active:
            return jsonify({"error": "Account is deactivated. Please contact support."}), 403

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()

        access_token = create_access_token(user.id, user.email, user.username)
        refresh_token = create_refresh_token(user.id)

        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user.to_dict(),
        })

    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500
    finally:
        db.close()


@app.route("/api/auth/refresh", methods=["POST"])
def refresh_token():
    """Exchange a refresh token for a new access token."""
    data = request.get_json()
    token = (data or {}).get("refresh_token") or extract_bearer_token(
        request.headers.get("Authorization")
    )

    if not token:
        return jsonify({"error": "Refresh token required"}), 400

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    user_id = int(payload["sub"])
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return jsonify({"error": "User not found or inactive"}), 401

        new_access = create_access_token(user.id, user.email, user.username)
        return jsonify({
            "access_token": new_access,
            "message": "Token refreshed successfully",
        })

    finally:
        db.close()


@app.route("/api/auth/me", methods=["GET"])
@login_required
def get_current_user():
    """Return the authenticated user's profile."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == g.current_user["user_id"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"user": user.to_dict()})
    finally:
        db.close()


# ============================================================================
# ROTATION ENDPOINTS  (public — no auth needed)
# ============================================================================

@app.route("/api/rotations", methods=["GET"])
def get_rotations():
    sm = _require(state_manager, "state_manager")
    rotations = sm.get_available_rotations()
    rotation_list = []
    for rotation in rotations:
        template = state_manager.get_template(rotation)
        if template:
            rotation_list.append({
                "id": rotation,
                "name": rotation.replace("_", " ").title(),
                "section_count": len(template.get("sections", [])),
                "version": template.get("version", "1.0"),
            })
    return jsonify({"rotations": rotation_list})


@app.route("/api/rotations/<rotation_id>", methods=["GET"])
def get_rotation_detail(rotation_id):
    sm = _require(state_manager, "state_manager")
    template = sm.get_template(rotation_id)
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    sections = sorted(template.get("sections", []), key=lambda s: s.get("order", 999))
    return jsonify({
        "id": rotation_id,
        "name": rotation_id.replace("_", " ").title(),
        "version": template.get("version", "1.0"),
        "sections": [
            {
                "name": s.get("name"),
                "title": s.get("title"),
                "order": s.get("order"),
                "required": s.get("required", True),
                "field_count": len(s.get("fields", [])),
            }
            for s in sections
        ],
    })


@app.route("/api/rotations/<rotation_id>/template", methods=["GET"])
def get_rotation_template(rotation_id):
    sm = _require(state_manager, "state_manager")
    template = sm.get_template(rotation_id)
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    return jsonify(template)


@app.route("/api/rotations/<rotation_id>/sections/<section_name>", methods=["GET"])
def get_section_template(rotation_id, section_name):
    sm = _require(state_manager, "state_manager")
    template = sm.get_template(rotation_id)
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    for section in template.get("sections", []):
        if section.get("name") == section_name:
            return jsonify(section)
    return jsonify({"error": "Section not found"}), 404


# ============================================================================
# CASE MANAGEMENT
# ============================================================================

@app.route("/api/cases", methods=["POST"])
@login_required
def create_case():
    """Create a new clerking case (requires authentication)."""
    sm = _require(state_manager, "state_manager")
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    rotation = data.get("rotation")
    if not rotation:
        return jsonify({"error": "rotation is required"}), 400

    try:
        case = state_manager.create_case(rotation)

        # Attach case to the authenticated user
        _link_case_to_user(case["case_id"], g.current_user["user_id"])

        return jsonify({
            "message": "Case created successfully",
            "case": {
                "case_id": case["case_id"],
                "rotation": case["rotation"],
                "current_section": case["current_section"],
                "created_at": case["created_at"],
                "is_complete": case["is_complete"],
            },
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to create case: {str(e)}"}), 500


@app.route("/api/cases", methods=["GET"])
@optional_auth
def list_cases():
    """
    List cases.
    When authenticated returns only the caller's cases.
    When unauthenticated (dev/demo mode) returns all cases.
    """
    sm = _require(state_manager, "state_manager")
    try:
        cases = sm.get_all_cases()

        if g.current_user:
            user_id = g.current_user["user_id"]
            cases = _filter_cases_by_user(cases, user_id)

        return jsonify({"cases": cases, "total": len(cases)})
    except Exception as e:
        return jsonify({"error": f"Failed to list cases: {str(e)}"}), 500


@app.route("/api/cases/<case_id>", methods=["GET"])
@optional_auth
def get_case(case_id):
    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    # Ownership check when authenticated
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    return jsonify(case)


@app.route("/api/cases/<case_id>", methods=["DELETE"])
@login_required
def delete_case(case_id):
    if not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    success = state_manager.delete_case(case_id)
    if not success:
        return jsonify({"error": "Case not found"}), 404
    return jsonify({"message": "Case deleted successfully", "case_id": case_id})


# ============================================================================
# SECTION ENDPOINTS
# ============================================================================

@app.route("/api/cases/<case_id>/sections/<section_name>", methods=["GET"])
@optional_auth
def get_section(case_id, section_name):
    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    sections = case.get("sections", {})
    if section_name not in sections:
        return jsonify({"error": "Section not found"}), 404

    section = sections[section_name]
    return jsonify({
        "case_id": case_id,
        "section_name": section_name,
        "data": section["data"],
        "status": section["status"],
        "pending_clarifications": section["pending_clarifications"],
    })


@app.route("/api/cases/<case_id>/sections/<section_name>", methods=["PUT"])
@optional_auth
def update_section(case_id, section_name):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    if section_name not in case.get("sections", {}):
        return jsonify({"error": "Section not found"}), 404

    section_data = data.get("data", {})
    status = data.get("status")

    try:
        updated = state_manager.update_section(case_id, section_name, section_data, status)
        return jsonify({
            "message": "Section updated successfully",
            "case_id": case_id,
            "section_name": section_name,
            "status": updated["sections"][section_name]["status"],
        })
    except Exception as e:
        return jsonify({"error": f"Failed to update section: {str(e)}"}), 500


@app.route("/api/cases/<case_id>/sections/<section_name>/submit", methods=["POST"])
@optional_auth
def submit_section(case_id, section_name):
    """Submit section data and trigger clarification engine."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    if section_name not in case.get("sections", {}):
        return jsonify({"error": "Section not found"}), 404

    section_data = data.get("data", {})

    try:
        # Persist the data first
        case = state_manager.update_section(
            case_id, section_name, section_data, SectionStatus.IN_PROGRESS.value
        )

        template = state_manager.get_template(case["rotation"])
        all_sections = {
            name: {"data": s["data"]}
            for name, s in case["sections"].items()
        }

        clarification_result = clarification_engine.process_section(
            case_id=case_id,
            section_name=section_name,
            section_data=section_data,
            template=template,
            all_sections=all_sections,
        )

        if clarification_result.questions:
            state_manager.add_clarifications(
                case_id, section_name, clarification_result.questions
            )
            return jsonify({
                "message": "Clarifications needed",
                "case_id": case_id,
                "section_name": section_name,
                "clarifications_needed": True,
                "questions": clarification_result.questions,
                "source": clarification_result.source,
                "confidence": clarification_result.confidence,
            })

        # No clarifications — mark complete
        state_manager.update_section(
            case_id, section_name, section_data, SectionStatus.COMPLETE.value
        )
        return jsonify({
            "message": "Section submitted successfully",
            "case_id": case_id,
            "section_name": section_name,
            "clarifications_needed": False,
            "status": SectionStatus.COMPLETE.value,
        })

    except Exception as e:
        return jsonify({"error": f"Failed to submit section: {str(e)}"}), 500


@app.route("/api/cases/<case_id>/sections/<section_name>/clarifications", methods=["POST"])
@optional_auth
def answer_clarifications(case_id, section_name):
    """Merge clarification answers into section data and mark complete."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    if section_name not in case.get("sections", {}):
        return jsonify({"error": "Section not found"}), 404

    answers = data.get("answers", {})

    try:
        existing = case["sections"][section_name]["data"]
        merged = {**existing, **answers}

        state_manager.update_section(
            case_id, section_name, merged, SectionStatus.COMPLETE.value
        )
        state_manager.clear_clarifications(case_id, section_name)

        return jsonify({
            "message": "Clarifications answered successfully",
            "case_id": case_id,
            "section_name": section_name,
            "status": SectionStatus.COMPLETE.value,
        })

    except Exception as e:
        return jsonify({"error": f"Failed to answer clarifications: {str(e)}"}), 500


@app.route("/api/cases/<case_id>/sections/<section_name>/skip", methods=["POST"])
@optional_auth
def skip_section(case_id, section_name):
    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    if section_name not in case.get("sections", {}):
        return jsonify({"error": "Section not found"}), 404

    try:
        state_manager.update_section(
            case_id, section_name, {"_skipped": True}, SectionStatus.COMPLETE.value
        )
        return jsonify({
            "message": "Section skipped",
            "case_id": case_id,
            "section_name": section_name,
            "status": SectionStatus.COMPLETE.value,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to skip section: {str(e)}"}), 500


# ============================================================================
# WORKFLOW ENDPOINTS
# ============================================================================

@app.route("/api/cases/<case_id>/next", methods=["POST"])
@optional_auth
def move_to_next_section(case_id):
    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    try:
        updated = state_manager.move_to_next_section(case_id)
        return jsonify({
            "message": "Moved to next section",
            "case_id": case_id,
            "current_section": updated["current_section"],
            "is_complete": updated["is_complete"],
            "completed_sections": updated["completed_sections"],
        })
    except Exception as e:
        return jsonify({"error": f"Failed to advance section: {str(e)}"}), 500


@app.route("/api/cases/<case_id>/progress", methods=["GET"])
@optional_auth
def get_progress(case_id):
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403
    try:
        return jsonify(state_manager.get_progress(case_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get progress: {str(e)}"}), 500


# ============================================================================
# PARSING ENDPOINTS  (public)
# ============================================================================

@app.route("/api/parse", methods=["POST"])
def parse_input():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    text = data.get("text")
    section = data.get("section", "general")
    if not text:
        return jsonify({"error": "text is required"}), 400
    try:
        return jsonify(input_parser.parse(text, section))
    except Exception as e:
        return jsonify({"error": f"Failed to parse input: {str(e)}"}), 500


@app.route("/api/parse/socrates", methods=["POST"])
def parse_socrates():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    text = data.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400
    try:
        socrates = input_parser._extract_socrates_pain(text)
        return jsonify(socrates.to_dict() if socrates else {
            "site": None, "onset": None, "character": None,
            "radiation": None, "associations": None, "time_course": None,
            "exacerbating": None, "relieving": None, "severity": None,
            "is_complete": False,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to parse SOCRATES: {str(e)}"}), 500


# ============================================================================
# CLARIFICATION ENDPOINTS  (public)
# ============================================================================

@app.route("/api/clarify", methods=["POST"])
def generate_clarifications():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    section_name = data.get("section_name")
    section_data = data.get("section_data", {})
    rotation = data.get("rotation")
    if not section_name or not rotation:
        return jsonify({"error": "section_name and rotation are required"}), 400
    template = state_manager.get_template(rotation)
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    try:
        result = clarification_engine.process_section(
            case_id="temp",
            section_name=section_name,
            section_data=section_data,
            template=template,
        )
        return jsonify({
            "questions": result.questions,
            "source": result.source,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to generate clarifications: {str(e)}"}), 500


@app.route("/api/clarify/contradictions", methods=["POST"])
def detect_contradictions():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    sections = data.get("sections", {})
    try:
        contradictions = clarification_engine.detect_contradictions(sections)
        return jsonify({
            "contradictions_found": len(contradictions) > 0,
            "contradictions": contradictions,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to detect contradictions: {str(e)}"}), 500


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@app.route("/api/cases/<case_id>/export", methods=["POST"])
@optional_auth
def export_case(case_id):
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json() or {}
    format_type = data.get("format", "markdown")
    include_sections = data.get("sections")

    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    try:
        if format_type == "markdown":
            result = document_compiler.compile_markdown(case_id, case, include_sections)
        elif format_type == "word":
            result = document_compiler.compile_word(case_id, case, include_sections)
        else:
            return jsonify({"error": "Invalid format. Use 'markdown' or 'word'"}), 400

        if result.success:
            return jsonify({
                "message": f"Case exported to {format_type} successfully",
                "case_id": case_id,
                "format": format_type,
                "file_path": result.file_path,
                "content": result.content if format_type == "markdown" else None,
            })
        return jsonify({"error": result.error}), 500

    except Exception as e:
        return jsonify({"error": f"Failed to export case: {str(e)}"}), 500


@app.route("/api/cases/<case_id>/export/download", methods=["GET"])
@optional_auth
def download_export(case_id):
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    format_type = request.args.get("format", "markdown")
    ext = "md" if format_type == "markdown" else "docx"
    file_path = os.path.join(document_compiler.output_dir, f"{case_id}.{ext}")
    mimetype = (
        "text/markdown"
        if format_type == "markdown"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    if not os.path.exists(file_path):
        return jsonify({"error": "Export not found. Please export the case first."}), 404

    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"clerkase_{case_id}.{ext}",
    )


@app.route("/api/cases/<case_id>/summary", methods=["GET"])
@optional_auth
def get_case_summary(case_id):
    if g.current_user and not _user_owns_case(case_id, g.current_user["user_id"]):
        return jsonify({"error": "Access denied"}), 403

    case = state_manager.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    try:
        result = document_compiler.compile_case_summary(case_id, case)
        if result.success:
            return jsonify({"case_id": case_id, "summary": result.content})
        return jsonify({"error": result.error}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to generate summary: {str(e)}"}), 500


# ============================================================================
# OWNERSHIP HELPERS  (private)
# ============================================================================

def _link_case_to_user(case_id: str, user_id: int) -> None:
    """Set user_id on a freshly created Case row."""
    from database import SessionLocal as _SL
    from database.models import Case as _Case
    db = _SL()
    try:
        row = db.query(_Case).filter(_Case.case_id == case_id).first()
        if row:
            row.user_id = user_id
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _user_owns_case(case_id: str, user_id: int) -> bool:
    """Return True if the Case row's user_id matches user_id (or has no owner)."""
    from database import SessionLocal as _SL
    from database.models import Case as _Case
    db = _SL()
    try:
        row = db.query(_Case).filter(_Case.case_id == case_id).first()
        if not row:
            return False
        # Cases with no owner are accessible to everyone (dev / demo mode)
        return row.user_id is None or row.user_id == user_id
    finally:
        db.close()


def _filter_cases_by_user(cases: list, user_id: int) -> list:
    """Return only cases owned by user_id (or ownerless cases)."""
    from database import SessionLocal as _SL
    from database.models import Case as _Case
    db = _SL()
    try:
        rows = (
            db.query(_Case.case_id)
            .filter(
                (_Case.user_id == user_id) | (_Case.user_id == None)  # noqa: E711
            )
            .all()
        )
        allowed = {r.case_id for r in rows}
        return [c for c in cases if c["case_id"] in allowed]
    finally:
        db.close()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    os.makedirs("exports", exist_ok=True)

    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   ClerKase — AI Clinical Clerking Assistant                  ║
║   API Server Starting on port {port:<5}                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

    app.run(host="0.0.0.0", port=port, debug=debug)
