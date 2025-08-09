from fastapi import FastAPI, UploadFile, File, Request
from google.cloud import storage
import uuid, os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from invention_detection_classification_agent.vertex_query import run_idca

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


@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    try:
        blob_name = f"{uuid.uuid4()}-{file.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, rewind=True)
        gcs_uri = f"gs://{bucket_name}/{blob_name}"

        idca_result = run_idca(gcs_uri)

        return {"uri": gcs_uri, "result": idca_result}
    except Exception as e:
        return {"error": str(e)}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Print error for logging/debugging
    print(f"Unhandled_exception: {exc}")

    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
        headers={"Access-Control-Allow-Origin": "*",
                 "Access-Control-Allow-Methods": "*",
                 "Access-Control-Allow-Headers": "*"},
    )