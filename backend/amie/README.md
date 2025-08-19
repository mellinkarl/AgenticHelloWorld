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
pip install -r requirements.txt
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
{ "request_id": "068dae74-0218-43ed-8482-d0d271e4bb99" }
```

---

### GET /state/{request\_id}

Query the latest graph state by request\_id:

```json
[
  {
    "messages": [],
    "request_id": "068dae74-0218-43ed-8482-d0d271e4bb99",
    "doc_uri": "gs://bucket/file.pdf",
    "metadata": {
      "author": "Alice",
      "field": "AI"
    },
    "manuscript_text": "This is a sample manuscript.",
    "idca": {
      "status": "present",
      "summary": "MVP placeholder summary",
      "fields": [
        "demo"
      ],
      "reasoning": "Placeholder reasoning"
    },
    "novelty": {
      "novel": true,
      "matches": [],
      "reasoning": "Placeholder novelty reasoning"
    },
    "report": {
      "status": "MVP",
      "note": "Pipeline skeleton executed successfully"
    },
    "errors": [],
    "logs": [
      "Ingestion placeholder ran",
      "IDCA placeholder ran",
      "Novelty placeholder ran",
      "Aggregation placeholder ran"
    ]
  },
  [],
  {
    "configurable": {
      "thread_id": "068dae74-0218-43ed-8482-d0d271e4bb99",
      "checkpoint_ns": "",
      "checkpoint_id": "1f07b2b7-d975-670a-8005-a077a4c4708f"
    }
  },
  {
    "source": "loop",
    "step": 5,
    "parents": {}
  },
  "2025-08-17T05:31:56.936567+00:00",
  {
    "configurable": {
      "thread_id": "068dae74-0218-43ed-8482-d0d271e4bb99",
      "checkpoint_ns": "",
      "checkpoint_id": "1f07b2b7-d973-6932-8004-1b4ed4e381a8"
    }
  },
  [],
  []
]

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