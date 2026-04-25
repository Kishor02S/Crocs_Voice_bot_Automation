# Automaton — Crocs Order Bot

AI-powered outbound calling bot that takes Crocs orders from customers in English, Hindi, Kannada, and Marathi.

---

## How it works

```
Dashboard → Enter phone number → Click "Call & Take Order"
        ↓
Bland.ai makes a real phone call to customer
        ↓
AI bot greets → asks which Crocs → asks quantity → confirms order
        ↓
Bland.ai sends webhook → Flask parses order → saves to SQLite DB
        ↓
Order appears in dashboard
```

---

## Setup

### Step 1 — Get Bland.ai API key (free)
1. Go to https://app.bland.ai
2. Sign up (free account)
3. Go to Settings → API Keys → Copy your key

### Step 2 — Set API key
Open `app.py` and replace line:
```python
BLAND_API_KEY = os.environ.get("BLAND_API_KEY", "YOUR_BLAND_API_KEY_HERE")
```
With your actual key, OR set it as an environment variable:
```bash
# Windows
set BLAND_API_KEY=your_key_here

# Mac/Linux
export BLAND_API_KEY=your_key_here
```

### Step 3 — Install & run
```bash
pip install flask
python app.py
```

### Step 4 — Expose webhook (for Bland.ai to send order data back)
Bland.ai needs to reach your Flask server. Use ngrok (free):
```bash
# Install ngrok from https://ngrok.com
ngrok http 5000
```
Copy the https URL (e.g. `https://abc123.ngrok.io`) and update `app.py`:
```python
"webhook": "https://abc123.ngrok.io/api/webhook/bland",
```

### Step 5 — Open dashboard
```
http://localhost:5000
```

---

## Products

| Product | Price |
|---|---|
| Classic Collection | ₹3,999 |
| Baya Clog | ₹4,499 |
| Baya Band | ₹2,999 |

---

## Languages supported
- English
- हिन्दी (Hindi)
- ಕನ್ನಡ (Kannada)
- मराठी (Marathi)

Bot detects language from customer's speech and responds accordingly.

---

## Folder structure
```
crocs_bot/
├── app.py              ← Flask backend + Bland.ai + SQLite
├── requirements.txt    ← pip install flask only
├── README.md
├── orders.db           ← auto-created on first run
└── templates/
    └── index.html      ← dashboard UI
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Dashboard |
| `/api/call` | POST | Trigger outbound call |
| `/api/orders` | GET | All orders |
| `/api/calls` | GET | Call log |
| `/api/stats` | GET | Summary stats |
| `/api/webhook/bland` | POST | Bland.ai webhook (auto) |
| `/api/call/status/<id>` | GET | Check call status |
