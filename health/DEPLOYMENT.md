# 🚀 MediLink AI — Real-World Deployment Guide

This guide provides step-by-step instructions to deploy **MediLink AI** to production cloud platforms.

---

## ⚡ Method 1: Free Cloud Deployment on Render (Easiest & Free)

Render allows you to host web applications for free with automatic SSL (`https://`).

### Steps:
1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit for MediLink AI deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/medilink-ai.git
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to [render.com](https://render.com) and sign up for a free account.
   - Click **New +** → **Web Service**.
   - Connect your GitHub repository `medilink-ai`.
   - Render will automatically detect settings from [Procfile](file:///c:/Users/saima/OneDrive/Desktop/health/Procfile) or [render.yaml](file:///c:/Users/saima/OneDrive/Desktop/health/render.yaml):
     - **Environment**: `Python`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
   - Under **Environment Variables**, add:
     - `SECRET_KEY`: `<Generate a random long string>`
     - `GEMINI_API_KEY`: `<Your Gemini key (optional)>`
   - Click **Create Web Service**. Done! Your app is live at `https://medilink-ai.onrender.com`.

---

## 🐳 Method 2: Docker Container Deployment (Universal)

Docker packages the app, Python runtime, and dependencies into a single container that runs on any server.

### Local or Cloud Server Run:

```bash
# Build the Docker image
docker build -t medilink-ai .

# Run container on port 5000
docker run -d -p 5000:5000 --name medilink_container medilink-ai
```

### Using Docker Compose:
```bash
docker-compose up -d --build
```
Your app will be running live at `http://localhost:5000`.

---

## 🚂 Method 3: Railway / Fly.io / Heroku

1. Link your GitHub repository to [Railway.app](https://railway.app) or [Fly.io](https://fly.io).
2. Railway detects [Procfile](file:///c:/Users/saima/OneDrive/Desktop/health/Procfile) and deploys automatically with zero extra configuration.
3. Set your environment variables (`SECRET_KEY`) in the service dashboard.

---

## 🛡️ Production Checklist

- [x] **WSGI HTTP Server**: Production configured with `Gunicorn` (Linux) / `Waitress` (Windows).
- [ ] **Secret Key**: Ensure `SECRET_KEY` in environment variables is changed from default.
- [ ] **Domain & SSL**: Enable HTTPS (handled automatically by Render/Railway).
- [ ] **Database Persistence**: Ensure SQLite file (`database.db`) is mounted on a persistent disk or migrated to PostgreSQL for high traffic.
