# AMIE MVP Skeleton

A **FastAPI + LangGraph**-based skeleton system for scientific manuscript analysis.  
This MVP implements the full pipeline flow (Ingestion → IDCA → NAA → Aggregation) with placeholder agents.  
⚠️ **No LLM integration yet** – current version is for testing graph execution only.

---

## Run Locally

### 1. Create virtual environment
```bash
python3 -m venv .venv


### 2. Activate environment

```bash
# macOS/Linux (bash/zsh)
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.in
```

### 4. Start backend service

```bash
# Disable __pycache__ generation
PYTHONDONTWRITEBYTECODE=1 uvicorn amie.app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## API Endpoints

### Swagger UI

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### ReDoc

[http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

### POST /invoke

Submit a document URL + metadata:

```bash
curl -X POST "http://127.0.0.1:8000/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "gcs_url": "gs://bucket/file.pdf",
           "metadata": { "author": "Alice", "field": "AI" }
         }'
```

Response example:

```json
{ "request_id": "uuid-1234" }
```

---

### GET /state/{request\_id}

Query the latest graph state by request\_id:

```bash
curl "http://127.0.0.1:8000/state/uuid-1234"
```

* HTTP response: checkpointed state
* Backend logs: full JSON-dumped GraphState (for debugging)

---

## TODO

### High Priority

* [ ] Integrate the **first LLM node** into the pipeline
* [ ] Explore **Google Cloud storage** for PDF and `.db` persistence
* [ ] Implement real logic for **Ingestion Agent (IA)**

### Medium Priority

* [ ] Support automatic switching between `SqliteSaver("checkpoint.db")` (local) and `MemorySaver` (cloud/ADC)

### Low Priority

* [ ] Define **Swagger interface schema** (pending design)

---

## Author

Harry
2025-08-16