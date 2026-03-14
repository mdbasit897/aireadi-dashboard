# Deployment Guide — Azure VM

This guide walks you through deploying the AI-READI Dashboard on your Azure VM for the hospital demo.

---

## Option A — Direct (no Docker, fastest for demo)

### 1. Prerequisites on the VM

```bash
# Python 3.10+
python3 --version

# Node.js 18+
node --version

# Install system deps if needed
sudo apt update && sudo apt install -y python3-pip nodejs npm
```

### 2. Clone the repository

```bash
cd ~
git clone https://github.com/your-username/aireadi-dashboard.git
cd aireadi-dashboard
```

### 3. Configure environment

```bash
cp .env.example .env
nano .env
# Set DATASET_ROOT=/home/azureuser/Datasets/f9e65119-3f27-4525-a140-b4413222991d/dataset
# Optionally set ANTHROPIC_API_KEY for live AI summaries
```

### 4. Verify the dataset

```bash
cd scripts
pip3 install python-dotenv pydantic-settings --break-system-packages
python3 verify_dataset.py
```

All green ticks = ready.

### 5. Start the backend

```bash
cd ~/aireadi-dashboard/backend
pip3 install -r requirements.txt --break-system-packages
uvicorn main:app --host 0.0.0.0 --port 8000
```

Leave this terminal open (or use `tmux` / `screen`):

```bash
# In a new terminal:
tmux new -s backend
cd ~/aireadi-dashboard/backend
uvicorn main:app --host 0.0.0.0 --port 8000
# Ctrl+B then D to detach
```

### 6. Build and serve the frontend

```bash
cd ~/aireadi-dashboard/frontend
npm install
npm run build

# Serve the built files (install serve once)
npm install -g serve
serve -s dist -l 5173
```

Or serve with Python:
```bash
cd dist && python3 -m http.server 5173
```

### 7. Open in browser

- On the VM itself:  `http://localhost:5173`
- From your laptop:  `http://<VM-PUBLIC-IP>:5173`

Make sure Azure Network Security Group allows **inbound TCP on ports 5173 and 8000**.

---

## Option B — Docker Compose (recommended for stability)

```bash
# Install Docker if not already installed
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# Build and start
cd ~/aireadi-dashboard
docker-compose up --build -d

# Check logs
docker-compose logs -f
```

Dashboard at `http://<VM-IP>:5173`

---

## Firewall / NSG Rules Required

| Port | Purpose             |
|------|---------------------|
| 5173 | Frontend (React)    |
| 8000 | Backend API         |

In Azure Portal → VM → Networking → Add inbound rule for ports 5173 and 8000.

---

## For the Demo: Dev mode (live reload)

If you want the dev server with live reload during the demo:

```bash
# Terminal 1 — backend
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend dev server
cd frontend && npm run dev -- --host 0.0.0.0
```

---

## Enable AI Summaries (Claude API)

1. Get your Anthropic API key from https://console.anthropic.com
2. Add to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Restart the backend.

The "Generate summary" button on the Patient page will now call Claude to produce AI-powered clinical summaries.

---

## Troubleshooting

**Backend says "participants.tsv not found"**
→ Double-check `DATASET_ROOT` in `.env`. Run `python3 scripts/verify_dataset.py`.

**ECG/CGM data shows "not found on disk"**
→ The file path conventions inside your dataset may differ slightly. Run `scripts/preprocess.py` to scan actual paths and build the index.

**CORS errors in browser**
→ Add your frontend URL to `CORS_ORIGINS` in `.env`.

**Port already in use**
→ `sudo lsof -i :8000` then `kill <PID>`.
