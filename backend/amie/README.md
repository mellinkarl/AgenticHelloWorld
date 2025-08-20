# AMIE - AI Manuscript Intelligence Engine

> **A FastAPI + LangGraph-based intelligent system for scientific manuscript analysis and evaluation**

AMIE (AI Manuscript Intelligence Engine) is an intelligent system built with FastAPI and LangGraph, specifically designed for scientific manuscript analysis, classification, and evaluation. The system implements a complete pipeline flow from document ingestion to final report generation.

## 🚀 Features

- **Complete Agent Pipeline**: Ingestion → IDCA → Conditional Routing → Aggregation
- **Conditional Routing**: Smart routing based on IDCA status (present → NAA, implied/absent → AA)
- **Asynchronous Processing**: Background task processing with immediate request ID return
- **State Management**: Complete request state tracking and persistence
- **RESTful API**: Clear API interfaces with Swagger documentation
- **Google Cloud Integration**: Support for GCS document storage and Vertex AI
- **Modular Design**: Easily extensible and maintainable agent architecture

## 🏗️ System Architecture

``` log
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Ingestion   │ -> │ IDCA        │ -> │ Conditional │
│ Agent (IA)  │    │ Agent       │    │ Routing     │
└─────────────┘    └─────────────┘    └─────────────┘
                                            │
                                            ├─ status="present" ──────> ┌─────────────┐
                                            │                           │ Novelty A   │
                                            │                           │ Agent (NAA) │──┐
                                            │                           └─────────────┘  │
                                            │                                            │
                                            └─ status="implied/absent" ──────────────────┴──> ┌─────────────┐
                                                                                              │ AGGREGATION │ 
                                                                                              │ Agent (AA)  │──> END
                                                                                              └─────────────┘
```


### Agent Flow Logic

- **IA (Ingestion Agent)**: Document parsing and preprocessing
- **IDCA (Invention Detection & Classification Agent)**: Invention detection and classification
  - **Conditional Routing**:
    - If `status = "present"` → Continue to **NAA (Novelty Assessment Agent)**
    - If `status = "implied"` or `"absent"` → Skip to **AA (Aggregation Agent)**
- **NAA (Novelty Assessment Agent)**: Novelty assessment (only runs when invention is present)
- **AA (Aggregation Agent)**: Result aggregation and report generation

## 🛠️ Quick Start

### Requirements

- Python 3.11+
- pip
- Virtual environment support

### 1. Clone Project

```bash
git clone <repository-url>
cd backend/amie
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
```

### 3. Activate Environment

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Start Service

```bash
# Disable Python bytecode cache
PYTHONDONTWRITEBYTECODE=1 uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Access API Documentation

- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## 📡 API Endpoints

### Submit Document Analysis Request

```bash
POST /invoke
```

**Request Example:**
```bash
curl -X POST "http://127.0.0.1:8000/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "gcs_url": "gs://bucket/document.pdf",
           "metadata": {
             "author": "John Smith",
             "field": "Artificial Intelligence",
             "journal": "Nature",
             "year": 2024
           }
         }'
```

**Response Example:**
```json
{
  "request_id": "068dae74-0218-43ed-8482-d0d271e4bb99"
}
```

### Query Processing Status

```bash
GET /state/{request_id}
```

**Response Example:**
```json
{
  "request_id": "068dae74-0218-43ed-8482-d0d271e4bb99",
  "doc_uri": "gs://bucket/document.pdf",
  "metadata": {
    "author": "John Smith",
    "field": "Artificial Intelligence"
  },
  "status": "FINISHED",
  "idca": {
    "status": "present",
    "summary": "This research proposes a new deep learning architecture",
    "fields": ["Machine Learning", "Deep Learning"],
    "reasoning": "Innovative improvements based on Transformer"
  },
  "novelty": {
    "novel": true,
    "matches": [],
    "reasoning": "Significant improvements over existing methods"
  },
  "report": {
    "status": "COMPLETED",
    "note": "Analysis complete, document shows innovation"
  }
}
```

### Debug State Query

```bash
GET /debug_state/{request_id}
```

Returns complete internal state information for debugging and development.

## 🔧 Configuration

### Environment Variables

- `GOOGLE_APPLICATION_CREDENTIALS`: Google Cloud service account key path
- `VERTEX_AI_PROJECT_ID`: Google Cloud project ID
- `VERTEX_AI_LOCATION`: Vertex AI service region

### Dependencies

Key dependencies include:
- **FastAPI**: Web framework
- **LangGraph**: Agent orchestration
- **Google Cloud**: Storage and AI services
- **Pydantic**: Data validation

## 🚧 Development Status

### ✅ Completed

- [x] Basic architecture setup
- [x] Agent pipeline framework
- [x] Conditional routing logic (IDCA → NAA/AA)
- [x] API interface design
- [x] State management system
- [x] Basic error handling

### 🔄 In Progress

- [ ] LLM node integration
- [ ] Google Cloud storage optimization
- [ ] Real agent logic implementation

### 📋 Planned

- [ ] Auto-deployment configuration
- [ ] Performance monitoring
- [ ] User authentication
- [ ] Batch processing support

## 🧪 Testing

```bash
# Run tests
pytest

# Run specific tests
pytest tests/test_agents/

# Generate coverage report
pytest --cov=app tests/
```

## 📦 Deployment

### Docker Deployment

```bash
# Build image
docker build -t amie-api .

# Run container
docker run -p 8000:8000 amie-api
```

### Google Cloud Run

```bash
# Deploy to Cloud Run
gcloud run deploy amie-api \
  --image gcr.io/PROJECT_ID/amie-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## 🤝 Contributing

Issues and Pull Requests are welcome!

### Development Guide

1. Fork the project
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👨‍💻 Author

**Harry**  
*2025-08-16*

---

## 📚 Related Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Google Cloud Documentation](https://cloud.google.com/docs)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
