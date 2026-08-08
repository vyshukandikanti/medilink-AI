# MediLink AI – Unified Health Record System

> **Hackathon-Ready Digital Healthcare Platform** featuring centralized patient records, standardized Health IDs (`MED-2026-0001`), AI clinical summaries, drug interaction analysis, interactive timelines, and simulated patient consent security.

---

## Key Highlights & Updates

- **Clean User-Driven Database**: Starts with 0 pre-loaded demo records. Only user-created patients and medical records are stored and rendered across the dashboard, search results, and timeline.
- **Simplified Medical Record Schema**: Doctor Name field removed for streamlined clinical record entry.
- **Unified Health ID & QR Codes**: Standardized Health IDs (e.g., `MED-2026-0001`) with real-time client-side QR generation.
- **Dual-Engine AI Suite**:
  - **AI Clinical Summary**: Auto-condenses history records into structured bullet points.
  - **Drug Interaction Checker**: Evaluates dual-medication safety risks (e.g., Warfarin + Aspirin high-risk flags vs Paracetamol + Amoxicillin safe checks).
  - **Medical Jargon Explainer**: Translates ICD-10 medical notes into simple layperson language.
  - **Smart Semantic Search**: Natural language filtering across patient records.
  - **Risk Alert Matrix**: Auto-highlights drug allergies, asthma, diabetes, and heart disease.
- **Interactive Visual Timeline**: Chronological feed of hospital visits, diagnosis, prescriptions, and lab tests.
- **Simulated Patient Consent Security**: Verification popup before hospital staff can access confidential patient timelines.

---

## Tech Stack

- **Frontend**: HTML5, CSS3 (Custom Glassmorphism Design System), Vanilla JavaScript (No React, No Bootstrap)
- **Backend**: Python Flask
- **Database**: SQLite (`database.db`)
- **Visuals**: Chart.js (CDN), Font Awesome 6 (CDN), QRCode.js (CDN)

---

## Project Structure (Strict 10-File Specification)

```text
c:/Users/saima/OneDrive/Desktop/health/
├── app.py                # Flask Server & AI Logic Engine
├── requirements.txt      # Python dependencies
├── .env.example          # API Key & Server Environment configuration
├── .gitignore            # Git exclusion rules
├── templates/
│   └── index.html        # SPA Unified Healthcare Template
├── static/
│   ├── style.css         # Glassmorphism Design Tokens & CSS Animations
│   ├── script.js        # Controller & Chart/QR/AJAX Handlers
│   └── logo.png          # App Brand Icon
├── README.md             # Documentation & Setup Guide
└── database.db           # SQLite Database (Auto-created on launch)
```

---

## Quick Start Guide

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Live Server

```bash
python app.py
```

### 3. Open in Browser

Navigate to **`http://127.0.0.1:5000`** in your browser.

---

## Footer Credit

**© 2026 MediLink AI – Unified Health Record System.**  
*Created by Kandikanti Sri Vyshnavi Devi.*
