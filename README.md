# ⚡ QueryMind
### Multimodal Intelligent Natural Language Query System for DuckDB

> Enterprise-grade AI-powered data analytics platform. Query any CSV dataset using plain English, voice commands, or image-based input — powered by FLAN-T5, Whisper ASR, and DuckDB.

---

## 🏗️ Architecture

```
querymind/
├── backend/                   # Flask Python API
│   ├── app.py                 # Entry point
│   ├── models/
│   │   ├── flan_t5.py         # NL → SQL (FLAN-T5 LLM)
│   │   ├── whisper_asr.py     # Voice → Text (Whisper)
│   │   └── ocr_engine.py      # Image → Text (Tesseract)
│   ├── services/
│   │   ├── duckdb_service.py  # SQL execution engine
│   │   ├── validator.py       # SQL safety & formatting
│   │   ├── history_service.py # SQLite query history
│   │   ├── column_advisor.py  # AI column recommendations
│   │   └── export_service.py  # CSV / PDF / PNG export
│   ├── routes/
│   │   ├── query_routes.py    # /api/query/*
│   │   ├── upload_routes.py   # /api/upload/*
│   │   ├── history_routes.py  # /api/history/*
│   │   └── export_routes.py   # /api/export/*
│   └── requirements.txt
│
└── frontend/                  # React + Vite + Tailwind
    └── src/
        ├── App.jsx
        ├── store/AppStore.jsx  # Global state (useReducer)
        ├── api/client.js       # Axios API layer
        ├── components/
        │   ├── Sidebar/        # Navigation + upload + table list
        │   ├── QueryInput/     # Text / Voice / Image / SQL tabs
        │   ├── ResultsPane/    # Table + Chart view + export
        │   ├── SQLViewer/      # Syntax-highlighted SQL display
        │   ├── Charts/         # Recharts auto-chart detection
        │   └── ColumnAdvisor/  # AI column recommendations UI
        └── pages/
            ├── QueryPage.jsx   # Main query interface
            ├── HistoryPage.jsx # Query log with stats
            ├── SchemaPage.jsx  # Column types + stats + preview
            └── SettingsPage.jsx
```

---

## 🚀 Quick Start

### Prerequisites

| Tool      | Version    |
|-----------|------------|
| Python    | 3.10+      |
| Node.js   | 18+        |
| Tesseract | 5.x (optional, for image input) |

**Install Tesseract (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

**Install Tesseract (macOS):**
```bash
brew install tesseract
```

---

### 1. Backend

```bash
cd querymind/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
python app.py
# → Running on http://localhost:5000
```

> **Note on AI models:** FLAN-T5 (~3GB) and Whisper (~150MB) download automatically on first run. The system works immediately with a fast rule-based fallback if models are still loading.

---

### 2. Frontend

```bash
cd querymind/frontend

# Install packages
npm install

# Start the dev server
npm run dev
# → Running on http://localhost:3000
```

Open **http://localhost:3000** in your browser.

---

## 📖 Usage Guide

### Step 1 — Upload a Dataset
Click **"Upload CSV / TSV"** in the sidebar. The file loads into DuckDB instantly.

### Step 2 — Choose Input Mode

| Mode | How to use |
|------|-----------|
| **Text** | Type your question in plain English, press ⌘↵ |
| **Voice** | Click the mic button, speak your query, click stop |
| **Image** | Upload a photo/screenshot containing your query text |
| **Direct SQL** | Write raw SQL if you prefer manual control |

### Step 3 — View Results
- Switch between **Table** and **Chart** views
- Chart type is auto-detected (bar / line / pie / scatter)
- Download results as **CSV**, **PDF report**, or **PNG chart**

### Step 4 — Explore Schema
Go to the **Schema** page to see column types, min/max/avg stats, and a data preview.

---

## 🔌 API Reference

### Upload Dataset
```
POST /api/upload/csv
Content-Type: multipart/form-data
Body: file=<csv_file>

Response: { table_name, row_count, col_count, schema, stats, preview }
```

### Query — Natural Language
```
POST /api/query/text
{ "question": "Show total sales by region", "table_name": "sales" }

Response: { sql, result: { rows, columns, row_count, elapsed_ms, chart_hint }, recommendations }
```

### Query — Voice
```
POST /api/query/voice
Content-Type: multipart/form-data
Body: audio=<webm_file>, table_name=<name>

Response: { transcription, sql, result, recommendations }
```

### Query — Image (OCR)
```
POST /api/query/image
Content-Type: multipart/form-data
Body: image=<image_file>, table_name=<name>

Response: { extracted_text, sql, result, recommendations }
```

### Query — Direct SQL
```
POST /api/query/direct
{ "sql": "SELECT * FROM sales LIMIT 10", "table_name": "sales" }
```

### History
```
GET  /api/history/          → list all queries
GET  /api/history/stats     → total, success, avg_ms
DEL  /api/history/<id>      → delete one entry
DEL  /api/history/clear     → clear all
```

### Export
```
POST /api/export/csv         → download CSV
POST /api/export/pdf         → download styled PDF report
POST /api/export/chart       → download PNG chart
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| AI — SQL Gen | FLAN-T5 Large (google/flan-t5-large) |
| AI — Voice | OpenAI Whisper (base model) |
| AI — OCR | Tesseract 5 + pytesseract |
| AI — Columns | sentence-transformers (all-MiniLM-L6-v2) |
| Query Engine | DuckDB 0.10 (in-memory) |
| Backend | Flask 3.0 + Flask-CORS |
| History DB | SQLite (local file) |
| Export | Pandas + ReportLab + Matplotlib |
| Frontend | React 18 + Vite + Tailwind CSS |
| Charts | Recharts |
| Syntax HL | react-syntax-highlighter |
| State | React useReducer |

---

## 📊 SDG Alignment

- **SDG 4 — Quality Education:** Lowers barrier to data analytics for non-technical users
- **SDG 9 — Industry, Innovation & Infrastructure:** AI-powered database innovation

## 🎓 Program Outcomes

| PO | Description |
|----|-------------|
| PO1 | Engineering Knowledge: AI, ML, Database systems |
| PO2 | Problem Analysis: Limitations of SQL expertise barriers |
| PO3 | Design/Development: Multimodal database interaction |
| PO5 | Modern Tool Usage: Flask, DuckDB, Transformers |
| PO9 | Team Work: Collaborative implementation |
| PO12| Lifelong Learning: NLP and AI advancements |

---

## 👥 Team

| Name | Roll No |
|------|---------|
| Mithil S | 4VV22CI064 |
| Varshitha M A | 4VV23CI118 |
| Venkatesh R | 4VV23CI119 |

**Project Guide:** Prof. Harshith C, Dept of CSE (AIML)

---

## 📄 License

Academic project — VVCE, 2024–25
