# Nutrition Analysis Web Application

A production-ready nutrition analysis app with **authentication**, **AI-based image analysis**, and a modern health-tech UI. Users sign up, log in, upload food images, and get detailed nutrition data (calories, macros, vitamins/minerals) from the USDA database.

## Tech stack

- **Frontend:** HTML, Tailwind CSS, JavaScript (vanilla)
- **Backend:** Python, FastAPI
- **Database:** SQLite (SQLAlchemy)
- **Auth:** JWT (Bearer), bcrypt password hashing
- **AI:** ImageAI ResNet50 + USDA API for nutrition

## Step-by-step instructions

### 1. Install and run locally

```bash
cd fruits-Scanner
pip install -r requirements.txt
```

Ensure the ResNet50 model file `resnet50-19c8e357.pth` is in this folder or in the parent folder (see [download_model.py](download_model.py) for auto-download on deploy).

Optional environment variables:

- `USDA_API_KEY` – your [USDA API key](https://fdc.nal.usda.gov/api-key-signup.html) (default key may have limits)
- `SECRET_KEY` – JWT secret (set in production)
- `DATABASE_URL` – defaults to `sqlite:///./nutrition_app.db`

Run the server:

```bash
python app.py
```

Open **http://127.0.0.1:5002/** (or the port printed in the terminal).

### 2. Use the app

1. **Sign up** – Open the app; you’ll be redirected to `/login`. Click “Sign up”, enter Name, Email, Password (min 6 chars). Form validation and error messages are shown.
2. **Log in** – After signup (or on later visits), log in with Email and Password. You receive a JWT and are redirected to the dashboard.
3. **Dashboard** – Navbar: Home, Upload, How It Works, Logout. Scroll or use links to navigate.
4. **Upload** – In the Upload section, drag & drop or click to choose an image (JPG/PNG). The upload area is disabled while scanning; a progress bar and scanning animation run until the backend finishes.
5. **Results** – After analysis you see: food name, confidence %, calories, protein, fat, carbs, fiber, and vitamins/minerals when available from USDA.
6. **How It Works** – Step-by-step: Image upload → Image processing → Food recognition (AI) → Nutrition data mapping (USDA).
7. **Why This Project Is Important** – Benefits: healthy lifestyle, diet planning, fitness tracking, awareness about food nutrition.
8. **Logout** – Click Logout in the navbar to clear the session and return to the login page.

### 3. API overview

- `POST /api/signup` – Body: `{ "name", "email", "password" }` → returns `{ "access_token", "user" }`
- `POST /api/login` – Body: `{ "email", "password" }` → returns `{ "access_token", "user" }`
- `GET /api/me` – Header: `Authorization: Bearer <token>` → current user
- `POST /api/fruit-detection` – Header: `Authorization: Bearer <token>`, body: multipart `file` → detection + nutrition

Unauthenticated users are redirected to the login page from the dashboard. The fruit-detection API returns 401 without a valid token.

### 4. Database schema

**users**

| Column         | Type     | Description      |
|----------------|----------|------------------|
| id             | Integer  | Primary key      |
| name           | String   | User name        |
| email          | String   | Unique, indexed  |
| password_hash  | String   | Bcrypt hash      |
| created_at     | DateTime | Registration time|

Tables are created automatically on first run (`init_db()`).

## Quick start (summary)

1. `pip install -r requirements.txt`
2. (Optional) Set `USDA_API_KEY` and `SECRET_KEY`.
3. `python app.py`
4. Open **http://127.0.0.1:5002/** → sign up or log in → upload an image.
5. API docs: **http://127.0.0.1:5002/docs**

## Live deployment (Render)

To run the app live on the web:

1. Push this repo to GitHub (e.g. [fruits-Scanner](https://github.com/Rajshimpi2706/fruits-Scanner)).
2. Go to [Render Dashboard](https://dashboard.render.com) and sign in with GitHub.
3. Click **New** → **Web Service**.
4. Connect the `Rajshimpi2706/fruits-Scanner` repo (or your fork).
5. Render will use the `render.yaml` in the repo. Confirm:
   - **Build command:** `pip install -r requirements.txt && python download_model.py`
   - **Start command:** `python app.py`
6. Under **Environment**, add:
   - `USDA_API_KEY` – your [USDA API key](https://fdc.nal.usda.gov/api-key-signup.html)
   - `SECRET_KEY` – a long random string for JWT signing (e.g. 32+ characters)
7. Click **Create Web Service**. The first deploy may take 5–10 minutes (model download).
8. When it’s done, open the URL shown (e.g. `https://fruits-scanner.onrender.com`).

**Notes:**  
- On the free plan the service sleeps after ~15 minutes of no traffic; the first request after that may take 30–60 seconds to wake it up.  
- The AI model loads on the first image you upload (to stay under 512MB at startup). That first detection may take 30–60 seconds; later ones are faster. If the first detection fails with "out of memory", switch to a **Starter** plan (more RAM) in Render.

Notes
- This uses ImageAI ResNet50 (ImageNet) for prototyping. For better fruit detection, fine-tune a model on a fruit dataset.
