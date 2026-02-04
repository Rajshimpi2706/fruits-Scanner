import os
import tempfile
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from database import init_db, get_db, User
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_user_by_email,
    get_current_user,
    SignupRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
)

# ------------------ APP SETUP ------------------
app = FastAPI(title="Nutrition Analysis API")

# Create DB tables on startup
@app.on_event("startup")
def on_startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths relative to this file (works regardless of cwd)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ------------------ USDA CONFIG ------------------
USDA_API_KEY = os.getenv("USDA_API_KEY", "")
USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# ------------------ IMAGEAI MODEL (lazy load to stay under 512MB on Render) ------------------
_classifier = None

def _get_model_path():
    execution_path = os.getcwd()
    possible_paths = [
        os.path.join(BASE_DIR, "resnet50-19c8e357.pth"),
        os.path.join(execution_path, "resnet50-19c8e357.pth"),
        os.path.join(execution_path, "..", "resnet50-19c8e357.pth"),
        os.path.join(execution_path, "..", "FruitNutritionDetector", "resnet50-19c8e357.pth"),
    ]
    return next((os.path.abspath(p) for p in possible_paths if os.path.isfile(p)), None)

def get_classifier():
    """Load ImageAI classifier on first use so server can start within 512MB (Render free tier)."""
    global _classifier
    if _classifier is not None:
        return _classifier
    model_path = _get_model_path()
    if not model_path:
        raise RuntimeError("Model file resnet50-19c8e357.pth not found")
    import torch
    from imageai.Classification import ImageClassification
    _original_load = torch.load
    def patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _original_load(*args, **kwargs)
    torch.load = patched_load
    classifier = ImageClassification()
    classifier.setModelTypeAsResNet50()
    classifier.setModelPath(model_path)
    classifier.loadModel()
    _classifier = classifier
    return _classifier

# ------------------ USDA FUNCTIONS ------------------
def fetch_nutritional_data(food_name: str):
    response = requests.get(
        USDA_BASE_URL,
        params={
            "api_key": USDA_API_KEY,
            "query": food_name,
            "pageSize": 1
        },
        timeout=10
    )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="USDA API failed")

    return response.json()

# Core macros + common vitamins/minerals for UI
NUTRIENT_KEYS = {
    "Energy",
    "Protein",
    "Total lipid (fat)",
    "Carbohydrate, by difference",
    "Fiber, total dietary",
    "Vitamin A, RAE",
    "Vitamin C, total ascorbic acid",
    "Vitamin D (D2 + D3)",
    "Calcium, Ca",
    "Iron, Fe",
    "Sodium, Na",
    "Potassium, K",
}

def extract_nutrients(data):
    foods = data.get("foods")
    if not foods:
        return {"error": "No nutrition data found"}

    food = foods[0]
    nutrients = {}
    vitamins_minerals = {}

    for n in food.get("foodNutrients", []):
        name = n.get("nutrientName")
        value = n.get("value")
        if name in NUTRIENT_KEYS:
            nutrients[name] = value
        # Capture any vitamin/mineral-like names for extra display
        if value is not None and (
            "Vitamin" in (name or "")
            or "Calcium" in (name or "")
            or "Iron" in (name or "")
            or "Sodium" in (name or "")
            or "Potassium" in (name or "")
        ):
            vitamins_minerals[name] = value

    return {
        "food_name": food.get("description"),
        "nutrients": nutrients,
        "vitamins_minerals": vitamins_minerals,
    }

# ------------------ AUTH ROUTES ------------------
@app.post("/api/signup", response_model=TokenResponse)
def signup(body: SignupRequest, db=Depends(get_db)):
    name = (body.name or "").strip()
    email = (body.email or "").strip().lower()
    password = body.password or ""
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if get_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, name=user.name, email=user.email),
    )


@app.post("/api/login", response_model=TokenResponse)
def login(body: LoginRequest, db=Depends(get_db)):
    email = (body.email or "").strip().lower()
    password = body.password or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse(id=user.id, name=user.name, email=user.email),
    )


@app.get("/api/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(id=current_user.id, name=current_user.name, email=current_user.email)


# ------------------ PAGE ROUTES ------------------
@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.get("/signup")
def signup_page():
    return FileResponse(os.path.join(STATIC_DIR, "signup.html"))


# ------------------ PROTECTED API ------------------
@app.post("/api/fruit-detection")
async def fruit_detection(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name

    try:
        classifier = get_classifier()
        predictions, probabilities = classifier.classifyImage(temp_path, result_count=1)

        detected_fruit = predictions[0]
        confidence = round(float(probabilities[0]), 3)

        usda_data = fetch_nutritional_data(detected_fruit)
        nutrition_info = extract_nutrients(usda_data)

        return {
            "detected_fruit": detected_fruit,
            "confidence": confidence,
            "nutrition_info": nutrition_info,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "processing_failed", "detail": str(e)},
        )

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ------------------ RUN SERVER ------------------
def _port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True

if __name__ == "__main__":
    env_port = os.getenv("PORT")
    if env_port:
        # Render etc. set PORT (e.g. 10000); use it directly
        port = int(env_port)
    else:
        # Local: try 5002, then 5003, ...
        port = 5002
        while port < 5010 and _port_in_use(port):
            port += 1
        if port >= 5010:
            raise RuntimeError("No available port in range 5002-5009. Free port 5002 or set PORT=5002")
    print(f"\n  Open in browser:  http://127.0.0.1:{port}/\n")
    uvicorn.run("app:app", host="0.0.0.0", port=port)
