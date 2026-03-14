# AI-READI Clinical Analytics Dashboard

A clinical analytics dashboard for exploring the **AI-READI v3.0.0** flagship Type 2 Diabetes dataset — built for hospital demonstrations and research insights.

![Dashboard Preview](docs/preview.png)

---

## Overview

This dashboard enables clinicians and researchers to:
- Explore 2,280 participant cohorts across 4 diabetic severity groups
- Visualize ECG waveforms, CGM glucose traces, and wearable vitals per patient
- Track enrollment trends and modality coverage across 3 clinical sites
- Review AI-generated clinical summaries for individual patients

---

## Project Structure

```
aireadi-dashboard/
├── backend/               # FastAPI Python backend
│   ├── main.py            # API entry point
│   ├── routers/           # Route handlers (cohort, patient, ecg, cgm)
│   ├── services/          # Data loading services (WFDB, OMOP, Dexcom)
│   ├── models.py          # Pydantic response models
│   └── requirements.txt
├── frontend/              # React + Vite frontend
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Dashboard, Patient, Explorer pages
│   │   ├── hooks/         # Data fetching hooks
│   │   └── utils/         # Clinical helpers (TIR, glucose zones)
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   ├── preprocess.py      # One-time data indexing script
│   └── verify_dataset.py  # Sanity check dataset paths
├── data/
│   └── participants_index.json  # Pre-built participant index
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Access to the AI-READI dataset on your Azure VM

### 1. Clone and configure

```bash
git clone https://github.com/your-username/aireadi-dashboard.git
cd aireadi-dashboard
cp .env.example .env
# Edit .env — set DATASET_ROOT to your Azure dataset path
```

### 2. Run the indexing script (one-time)

```bash
cd scripts
pip install -r ../backend/requirements.txt
python preprocess.py
```

This scans the dataset directory and builds a fast lookup index at `data/participants_index.json`.

### 3. Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be at **http://localhost:5173**

### 5. (Optional) Docker

```bash
docker-compose up --build
```

---

## Dataset Path

Set in `.env`:
```
DATASET_ROOT=/home/azureuser/Datasets/f9e65119-3f27-4525-a140-b4413222991d/dataset
```

---

## Key Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/cohort/summary` | Aggregate cohort stats |
| `GET /api/cohort/enrollment` | Monthly enrollment timeline |
| `GET /api/patients` | Paginated participant list with filters |
| `GET /api/patients/{id}` | Single participant profile |
| `GET /api/patients/{id}/cgm` | CGM glucose trace |
| `GET /api/patients/{id}/ecg` | 12-lead ECG waveform data |
| `GET /api/patients/{id}/wearable` | Garmin wearable summary |
| `GET /api/patients/{id}/summary` | AI-generated clinical summary |

---

## Demo Notes

- **No PHI**: The dataset contains no Protected Health Information per HIPAA
- **Read-only**: The dashboard only reads data, never modifies it
- **Offline capable**: All data is local on the Azure VM; no external API calls (except optional Claude API for AI summaries)
- **License**: AI-READI custom license v2.0 — for Type 2 Diabetes research use only

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts, Tailwind CSS |
| Backend | FastAPI, WFDB, Pandas, Pydantic |
| Data formats | WFDB (ECG), OMOP CSV (clinical), Open mHealth JSON (CGM) |
| Deployment | Docker Compose on Azure VM |
