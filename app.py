import os
import tempfile
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ------------------ APP SETUP ------------------
app = FastAPI(title="Fruit Nutrition Detection API")

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
USDA_API_KEY = os.getenv("USDA_API_KEY", "PjcAGiGcTDQiMsiTSFbfR5rIvo8cd0SFUGQIkRP1")
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

def extract_nutrients(data):
    foods = data.get("foods")
    if not foods:
        return {"error": "No nutrition data found"}

    food = foods[0]
    nutrients = {}

    for n in food.get("foodNutrients", []):
        if n.get("nutrientName") in {
            "Energy",
            "Protein",
            "Total lipid (fat)",
            "Carbohydrate, by difference",
            "Fiber, total dietary",
        }:
            nutrients[n["nutrientName"]] = n.get("value")

    return {
        "food_name": food.get("description"),
        "nutrients": nutrients,
    }

# ------------------ ROUTES ------------------
@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.post("/fruit-detection")
async def fruit_detection(file: UploadFile = File(...)):
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
    default_port = int(os.getenv("PORT", "5002"))
    port = default_port
    while port < 5010 and _port_in_use(port):
        port += 1
    if port >= 5010:
        raise RuntimeError("No available port in range 5002-5009. Free port 5002 or set PORT=5002")
    if port != default_port:
        print(f"Port {default_port} in use. Using port {port} instead.")
    print(f"\n  Open in browser:  http://127.0.0.1:{port}/\n")
    uvicorn.run("app:app", host="0.0.0.0", port=port)
