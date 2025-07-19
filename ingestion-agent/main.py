from fastapi import FastAPI, UploadFile, File
from google.cloud import storage
import uuid, os
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your frontend domain for production
    allow_methods=["*"],
    allow_headers=["*"],
)


app = FastAPI()
bucket_name = os.environ.get("BUCKET_NAME", "amie-manuscripts")
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    blob_name = f"{uuid.uuid4()}-{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, rewind=True)
    return {"uri": f"gs://{bucket_name}/{blob_name}"}
