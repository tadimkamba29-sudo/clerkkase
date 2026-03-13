"""
Flask route decorators for ClerKase authentication.

Decorators
----------
@login_required
    Route must receive a valid Bearer token.
    Injects g.current_user = {user_id, email, username}.
    Returns 401 if token is missing or invalid.

@optional_auth
    Validates the token if one is present, but does NOT reject the
    request when no token is provided.
    Injects g.current_user when valid, otherwise g.current_user = None.
    Use this for routes that work anonymously but offer richer behaviour
    when the caller is authenticated (e.g. scoping cases to the user).
"""

from functools import wraps

from flask import g, jsonify, request

from .utils import decode_token, extract_bearer_token


def _load_user_from_request() -> bool:
    """
    Try to authenticate the incoming request.

    Sets g.current_user to the decoded payload dict on success,
    or to None when no / invalid token is present.

    Returns True if a valid token was found, False otherwise.
    """
    token = extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        g.current_user = None
        return False

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        g.current_user = None
        return False

    g.current_user = {
        "user_id": int(payload["sub"]),
        "email": payload.get("email"),
        "username": payload.get("username"),
    }
    return True


def login_required(f):
    """
    Decorator — rejects the request with HTTP 401 unless a valid
    access token is supplied in the Authorization header.

    Usage::

        @app.route('/api/cases', methods=['POST'])
        @login_required
        def create_case():
            user = g.current_user   # always populated here
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        authenticated = _load_user_from_request()
        if not authenticated:
            return jsonify({
                "error": "Authentication required",
                "message": "Please provide a valid Bearer token in the Authorization header",
            }), 401
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """
    Decorator — loads the user from the token if one is present, but
    does not block unauthenticated requests.

    Usage::

        @app.route('/api/cases', methods=['GET'])
        @optional_auth
        def list_cases():
            if g.current_user:
                # return only this user's cases
            else:
                # return all cases (dev / demo mode)
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        _load_user_from_request()
        return f(*args, **kwargs)
    return decorated
