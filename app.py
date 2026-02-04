import os
import re
import secrets
import time
from typing import Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
import uvicorn

# ------------------ App setup (Render-safe) ------------------
# No torch / tensorflow imports. Mock inference only.
app = FastAPI(title="Fruit Scanner Demo API")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ------------------ Simple auth (demo-safe) ------------------
# Persists while the process is running (meets requirement).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS: dict[str, dict[str, Any]] = {}  # email -> {name, email, password_hash}
SESSIONS: dict[str, str] = {}  # session_id -> email

SESSION_COOKIE = "session_id"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def _verify_password(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


def _get_session_email(request: Request) -> str | None:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    return SESSIONS.get(sid)


def require_user(request: Request) -> dict[str, Any]:
    email = _get_session_email(request)
    if not email or email not in USERS:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return USERS[email]


@app.post("/api/signup")
async def api_signup(payload: dict, response: Response):
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if email in USERS:
        raise HTTPException(status_code=400, detail="User already exists")

    USERS[email] = {"name": name, "email": email, "password_hash": _hash_password(password)}

    # Create session cookie
    sid = secrets.token_urlsafe(24)
    SESSIONS[sid] = email
    response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax")
    return {"message": "Signup successful", "user": {"name": name, "email": email}}


@app.post("/api/login")
async def api_login(payload: dict, response: Response):
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    user = USERS.get(email)
    if not user or not _verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    sid = secrets.token_urlsafe(24)
    SESSIONS[sid] = email
    response.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="lax")
    return {"message": "Login successful", "user": {"name": user["name"], "email": user["email"]}}


@app.post("/api/logout")
async def api_logout(request: Request, response: Response):
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        SESSIONS.pop(sid, None)
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "Logged out"}


@app.get("/api/me")
async def api_me(user: dict = Depends(require_user)):
    return {"name": user["name"], "email": user["email"]}


# ------------------ Mock prediction (/predict) ------------------
MOCK_FOODS = [
    {
        "name": "Apple",
        "nutrition": {
            "calories": 52,
            "carbs_g": 14,
            "protein_g": 0.3,
            "fat_g": 0.2,
            "fiber_g": 2.4,
            "vitamins_minerals": {"Vitamin C": "4.6 mg", "Potassium": "107 mg"},
        },
    },
    {
        "name": "Banana",
        "nutrition": {
            "calories": 89,
            "carbs_g": 23,
            "protein_g": 1.1,
            "fat_g": 0.3,
            "fiber_g": 2.6,
            "vitamins_minerals": {"Vitamin B6": "0.4 mg", "Potassium": "358 mg"},
        },
    },
    {
        "name": "Orange",
        "nutrition": {
            "calories": 47,
            "carbs_g": 12,
            "protein_g": 0.9,
            "fat_g": 0.1,
            "fiber_g": 2.4,
            "vitamins_minerals": {"Vitamin C": "53.2 mg", "Calcium": "40 mg"},
        },
    },
]


@app.post("/predict")
async def predict(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_user),
):
    # Validate
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image upload")

    # Artificial delay to simulate ML processing (demo-friendly)
    time.sleep(1.4)

    # Deterministic-ish mock: pick based on filename length
    idx = (len(file.filename or "") + int(time.time()) ) % len(MOCK_FOODS)
    chosen = MOCK_FOODS[idx]
    confidence = round(0.86 + (idx * 0.03), 2)

    return {
        "food": chosen["name"],
        "confidence": confidence,
        "nutrition": chosen["nutrition"],
        "note": "Mocked prediction (Render free-tier safe).",
    }


# ------------------ Pages ------------------
@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.get("/signup")
def signup_page():
    return FileResponse(os.path.join(STATIC_DIR, "signup.html"))


# ------------------ Local dev runner ------------------
if __name__ == "__main__":
    env_port = os.getenv("PORT")
    if env_port:
        port = int(env_port)
    else:
        # Local: pick the first free port from 5002-5010
        import socket
        port = 5002
        while port < 5011:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("0.0.0.0", port))
                    break
                except OSError:
                    port += 1
        if port >= 5011:
            raise RuntimeError("No available port in range 5002-5010")
    print(f"\nOpen in browser: http://127.0.0.1:{port}/\n")
    uvicorn.run("app:app", host="0.0.0.0", port=port)
