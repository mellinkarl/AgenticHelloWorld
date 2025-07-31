from fastapi import FastAPI, UploadFile, File, Request
from google.cloud import storage
import uuid, os
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_vertexai import ChatVertexAI
import vertexai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your frontend domain for production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize GCS client
bucket_name = os.environ.get("BUCKET_NAME")
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

# Initialize Vertex AI
project_id = os.environ.get("GCP_PROJET_ID")
region = os.environ.get("GCP_REGION")
vertexai.init(project=project_id, location=region)

llm = ChatVertexAI(
    model="gemini-1.5-pro",
    temperature=0.7,
    max_output_tokens=512,
)

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    blob_name = f"{uuid.uuid4()}-{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, rewind=True)
    return {"uri": f"gs://{bucket_name}/{blob_name}"}

@app.post("/query")
async def query(request: Request):
    data = await request.json()
    prompt = data.get("prompt")
    if not prompt:
        return {"error": "Prompt is required"}
    response = llm.invoke(prompt)
    return {"response": response.text}