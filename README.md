Fruit Nutrition Detector (raj folder)

Quick start

1. Install dependencies (preferably in a virtualenv):

   pip install -r requirements.txt

2. Ensure `resnet50-19c8e357.pth` is available in this folder or in `../FruitNutritionDetector/`.

3. Set USDA API key (example, Windows PowerShell):

   setx USDA_API_KEY "your_actual_api_key_here"
   Restart your terminal to make it effective.

4. Run the app:

   python app.py

5. Open the app (frontend + backend integrated):

   http://127.0.0.1:5002/

   If port 5002 is in use, run instead:
   uvicorn app:app --host 0.0.0.0 --port 5003
   then open http://127.0.0.1:5003/

6. API docs:

   http://127.0.0.1:5002/docs

## Live deployment (Render)

To run the app live on the web:

1. Push this repo to GitHub (e.g. [fruits-Scanner](https://github.com/Rajshimpi2706/fruits-Scanner)).
2. Go to [Render Dashboard](https://dashboard.render.com) and sign in with GitHub.
3. Click **New** → **Web Service**.
4. Connect the `Rajshimpi2706/fruits-Scanner` repo (or your fork).
5. Render will use the `render.yaml` in the repo. Confirm:
   - **Build command:** `pip install -r requirements.txt && python download_model.py`
   - **Start command:** `python app.py`
6. Under **Environment**, add `USDA_API_KEY` with your [USDA API key](https://fdc.nal.usda.gov/api-key-signup.html).
7. Click **Create Web Service**. The first deploy may take 5–10 minutes (model download).
8. When it’s done, open the URL shown (e.g. `https://fruits-scanner.onrender.com`).

**Notes:**  
- On the free plan the service sleeps after ~15 minutes of no traffic; the first request after that may take 30–60 seconds to wake it up.  
- The AI model loads on the first image you upload (to stay under 512MB at startup). That first detection may take 30–60 seconds; later ones are faster. If the first detection fails with "out of memory", switch to a **Starter** plan (more RAM) in Render.

Notes
- This uses ImageAI ResNet50 (ImageNet) for prototyping. For better fruit detection, fine-tune a model on a fruit dataset.
