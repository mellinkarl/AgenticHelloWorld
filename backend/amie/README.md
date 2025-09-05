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

#### 5.1 Could ADC
```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project aime-hello-world
gcloud config set project aime-hello-world

```

##### if not:
```bash
gcloud storage buckets create gs://aime-hello-world-amie-uswest1 \
  --location=us-west1 \
  --uniform-bucket-level-access
```

#### 5.1.1 Onetime use
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/Users/harryzhang/git/AgenticHelloWorld/backend/.keys/aime-hello-world-2cd68fc662f2.json
# export GCS_BUCKET=aime-hello-world-amie-uswest1
# export GCS_PREFIX=uploads/tmp
# export SIGNED_URL_TTL_SECONDS=3600
```

#### 5.1.2 revert Onetime use
```bash
unset GOOGLE_APPLICATION_CREDENTIALS
```

#### 5.3 service
```bash
PYTHONDONTWRITEBYTECODE=1 uvicorn amie.app.main:app --host 0.0.0.0 --port 8000 --reload
# PYTHONDONTWRITEBYTECODE=1 uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Access API Documentation

- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## 📡 API Endpoints

### Upload file (only accept .pdf and image format)

#### Local Bcakend Test
```bash
curl -F "file=@/Users/harryzhang/git/AgenticHelloWorld/test_Docs/2507.15693v1.pdf" http://localhost:8000/upload-file 
# + "return_signed_url=true" will return signed_url

curl -F "file=@/path/to/image.png" http://localhost:8000/upload-file
```

##### response:
```json
{"bucket":"aime-hello-world-amie-uswest1","object":"amie/tmp/51244eb813534209aac63841218bf44c.pdf","gs_url":"gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf","content_type":"application/pdf","size":36593100,"lifecycle":{"delete_after_days":7,"matches_prefix":"amie/tmp/","matches_suffix":[".pdf",".png",".jpg",".jpeg",".webp",".gif",".bmp",".tiff",".tif"]},"signed_url":"https://storage.googleapis.com/aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=amie-agent-sa%40aime-hello-world.iam.gserviceaccount.com%2F20250904%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20250904T013331Z&X-Goog-Expires=604800&X-Goog-SignedHeaders=host&X-Goog-Signature=82e6f985a6b3dbde5950524036ebd51ff605bf9709252e62b63ac0111136cc100835fc060f4d1fa5a8ccb770b0470bce7321dc3604e073b62a9c392e08f41f04da20ec5d9ac9339c037b5986e2294114f197b90fd13b861c95a5619adfb908a0acdfd8688bfee802b36e3c383659557fb3a38bc6b5797f4c83dbd42cf949f29cb065a90d45ceecd7fcfe4b62b715df38b2e0b6b426f8bbac0b88b2419239582bd88b7b4b7d0d81b01f433f72f6512e1f4f1badc69c9956681c95fa19a79857f2d0a4fc02023643f4911a02c4e71a12ee2da2261e21c67bbfd21d46d5f60271892d068dd486f3f59b733a012a624898c0d43b1835e734cf69c1cece2644b3bf6f","signed_url_expires_in":604800,"suggested_invoke_payload":{"gcs_url":"gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf","metadata":{"source":"upload-file"}}}%
```
#### Frontend use GET_URL to directely submit to GCS
```
N/A
```

### Submit Document Analysis Request

```bash
POST /invoke
```

**Request Example:**
```bash
curl -X POST "http://127.0.0.1:8000/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "gcs_url": "gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf",
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
  "request_id": "b060d513-13c2-4d86-8c88-8f602bffe052"
}
```

### Query Processing Status

```bash
curl -X GET http://127.0.0.1:8000/state/{b060d513-13c2-4d86-8c88-8f602bffe052}
```

**Response Example:**
```json
{"request_id":"b060d513-13c2-4d86-8c88-8f602bffe052","status":"FINISHED","created_at":"2025-09-04T02:45:55.127925+00:00","updated_at":"2025-09-04T02:45:56.306889+00:00","report":{"ingestion":{},"idca":{"status":"implied","summary":"Dummy IDCA summary","fields":["Robotics","Perception"],"reasoning":"Analyzed source: gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf"},"novelty":{},"verdict":"UNDECIDED (dummy)"}}%
```

### Debug State Query

```bash
curl -X GET http://127.0.0.1:8000/debug_state/{4f898083-4384-4877-b8d5-8a364fca7986}
```
#### Example output:
```json
{"messages":[],"documents":[],"generation":null,"attempted_generations":0,"request_id":"4f898083-4384-4877-b8d5-8a364fca7986","doc_gcs_uri":"gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf","doc_local_uri":"file:///var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986/document.pdf","metadata":{"author":"John Smith","field":"Artificial Intelligence","journal":"Nature","year":2024},"status":"FINISHED","created_at":"2025-09-04T03:41:35.809359+00:00","updated_at":"2025-09-04T03:41:37.614594+00:00","runtime":{"ia":{"status":"FINISHED","route":[]},"idca":{"status":"PENDING","route":[]},"naa":{"status":"PENDING","route":[]},"aa":{"status":"PENDING","route":[]}},"artifacts":{"ia":{"ok":true,"doc_uri":"gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf","storage":"gcs","bucket":"aime-hello-world-amie-uswest1","object":"amie/tmp/51244eb813534209aac63841218bf44c.pdf","size":36593100,"content_type":"application/pdf","updated_iso":"2025-09-04T01:33:31.542000+00:00","doc_local_uri":"file:///var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986/document.pdf","is_pdf":true},"idca":{"status":"implied","summary":"Dummy IDCA summary","fields":["Robotics","Perception"],"reasoning":"Analyzed source: None"},"report":{"ingestion":{},"idca":{"status":"implied","summary":"Dummy IDCA summary","fields":["Robotics","Perception"],"reasoning":"Analyzed source: None"},"novelty":{},"verdict":"UNDECIDED (dummy)"}},"internals":{"ia":{"used_client":"google-cloud-storage","cleanup_hint":"/var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986"},"idca":{"model_version":"idca-dummy-0","debug":"ok"},"naa":{},"aa":{"weights":{"idca":0.5,"naa":0.5},"merge_policy":"dummy-avg"}},"errors":[],"logs":["IA: downloaded object from GCS and cached to local temp. gcs=gs://aime-hello-world-amie-uswest1/amie/tmp/51244eb813534209aac63841218bf44c.pdf size=36593100B ct=application/pdf updated=2025-09-04T01:33:31.542000+00:00 local=file:///var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986/document.pdf. This path is intended for downstream agents during this run; cleanup should remove /var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986 after the graph completes.","IDCA: dummy classification done.","AA: dummy aggregation complete."]}%
```
Returns complete internal state information for debugging and development.

### local test tmp local file:
```bash
ls -lh /var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986
```

### remove tmp cache:
```bash
rm -rf /var/folders/r5/d0kzcw217pqd9tdz0cxr9rk40000gn/T/amie/4f898083-4384-4877-b8d5-8a364fca7986
```

## Agents
ia.py
- receive a **doc_gcs_uri** download and save to local tmp dir and put tmp dir to **doc_local_uri**
- TODO: auto clean up tmp dir after graph end
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

### 🔄 In Progress

- [ ] Real agent logic implementation (IA, IDCA, NAA, AA)  
  - [x] IA  
  - [x] IDCA  
  - [ ] NAA  
  - [ ] AA  
- [ ] LLM model initialization in `main`  
- [ ] Config setup  
- [ ] Switch to GenAI backend  

## #📌 Planned

- [ ] Auto-deployment configuration  
- [ ] Performance monitoring  
- [ ] User authentication  
- [ ] Batch processing support  

## 🧪 Testing
 NONE

## 📦 Deployment
 NONE

### Docker Deployment
 NONE

### Google Cloud Run
 NONE

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

This project is licensed under the MIT License.
---

## 📚 Related Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Google Cloud Documentation](https://cloud.google.com/docs)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
