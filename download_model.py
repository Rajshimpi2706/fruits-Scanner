"""Download ResNet50 model for ImageAI if not present. Used in cloud deploy (e.g. Render)."""
import os
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_NAME = "resnet50-19c8e357.pth"
MODEL_PATH = os.path.join(BASE_DIR, MODEL_NAME)
# PyTorch official weights (same file ImageAI ResNet50 expects)
MODEL_URL = "https://download.pytorch.org/models/resnet50-19c8e357.pth"

if __name__ == "__main__":
    if os.path.isfile(MODEL_PATH):
        print(f"Model already exists: {MODEL_PATH}")
    else:
        print(f"Downloading {MODEL_NAME} to {BASE_DIR}...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Done.")
