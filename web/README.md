# DeepRare Web Application

Web interface for the [DeepRare](https://github.com/MAGIC-AI4Med/DeepRare) rare disease diagnosis system.

## Architecture

```
web/
├── backend/          # FastAPI REST API
│   ├── app/
│   │   ├── main.py           # FastAPI app entry
│   │   ├── config.py         # Settings & env config
│   │   ├── models/schemas.py # Pydantic request/response models
│   │   ├── routers/          # API endpoints
│   │   │   ├── hpo.py        # HPO extraction
│   │   │   ├── diagnosis.py  # Phenotype & Gene diagnosis (SSE)
│   │   │   └── config_router.py  # Models & key validation
│   │   └── services/         # Business logic
│   │       ├── hpo_service.py
│   │       ├── diagnosis_service.py
│   │       └── model_manager.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/         # React + Vite + Tailwind CSS
    └── src/
        ├── components/       # Reusable UI components
        ├── pages/            # Route pages
        ├── i18n/             # Internationalization (EN/ES)
        ├── services/api.js   # API client + SSE streaming
        └── context/          # Settings context (API keys, theme)
```

## Features

- **HPO Extraction** — Extract phenotype terms from clinical text, map to HPO codes
- **Phenotype Diagnosis** — AI-powered rare disease diagnosis with SSE progress streaming
- **Gene-Aware Diagnosis** — Exomiser gene prioritization with VCF file upload
- **Multi-LLM Support** — Choose between OpenAI, Claude, Gemini, DeepSeek
- **Bilingual UI** — English and Spanish
- **Dark/Light Theme** — Toggle between themes

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- DeepRare dependencies installed (see parent README)

### Backend

```bash
cd web/backend
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and data paths

# Start server
python run.py
```

The API will be available at `http://localhost:8000` (docs at `/docs`).

### Frontend

```bash
cd web/frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

### API Keys

You can configure API keys either:
1. In the backend `.env` file (server-wide defaults)
2. In the web UI Settings page (per-session, stored in browser localStorage)

**Note:** An OpenAI API key is always required for embeddings and mini completions, even when using other LLM providers.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/config/models` | List available models |
| `POST` | `/api/config/validate-key` | Validate API key |
| `POST` | `/api/hpo/extract` | Extract HPO terms from text |
| `POST` | `/api/diagnosis/phenotype` | Run phenotype diagnosis (SSE) |
| `POST` | `/api/diagnosis/gene` | Run gene diagnosis (SSE + VCF upload) |
