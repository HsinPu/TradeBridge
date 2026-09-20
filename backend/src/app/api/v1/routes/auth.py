from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.core.auth import AdminAuth, COOKIE_NAME, SESSION_SECONDS

router = APIRouter()


@router.get("/session")
def session(request: Request):
    auth: AdminAuth = request.app.state.admin_auth
    local = auth.local(request)
    authenticated = local or auth.authenticated(request)
    return {"login_required": not local, "authenticated": authenticated,
            "username": auth.settings.admin_username if authenticated and not local else None}


@router.post("/login")
async def login(request: Request):
    auth: AdminAuth = request.app.state.admin_auth
    if not auth.allow_attempt(request):
        return JSONResponse({"detail": "Too many login attempts"}, status_code=429,
                            headers={"Retry-After": "60"})
    # Avoid validation responses that reflect submitted passwords.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            return JSONResponse({"detail": "Invalid login request"}, status_code=400)
    import json
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        payload = None
    if not isinstance(payload, dict):
        return JSONResponse({"detail": "Invalid login request"}, status_code=400)
    username, password = payload.get("username"), payload.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 128 or len(password) > 1024:
        return JSONResponse({"detail": "Invalid login request"}, status_code=400)
    if not auth.verify_credentials(username, password):
        return JSONResponse({"detail": "Invalid username or password"}, status_code=401)
    token = auth.create_session(request)
    response = JSONResponse({"login_required": True, "authenticated": True,
                             "username": auth.settings.admin_username})
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, **auth.cookie_options())
    return response


@router.post("/logout", status_code=204)
def logout(request: Request):
    auth: AdminAuth = request.app.state.admin_auth
    auth.revoke(request)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, **auth.cookie_options())
    return response
