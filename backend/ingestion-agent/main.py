from fastapi import FastAPI, UploadFile, File, Request
from google.cloud import storage
import uuid, os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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




@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    try:
        blob_name = f"{uuid.uuid4()}-{file.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.file, rewind=True)
        return {"uri": f"gs://{bucket_name}/{blob_name}"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/query")
async def query(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt")
        gcs_uri = data.get("gcs_uri")
        if not prompt:
            return {"error": "Prompt and URI required"}
        
        # Initialize Vertex AI
        project_id = os.environ.get("GCP_PROJECT_ID")
        region = os.environ.get("GCP_REGION")
        vertexai.init(project=project_id, location=region)
        llm = ChatVertexAI(
            model="gemini-1.5-pro",
            temperature=0.7,
            max_output_tokens=512,
        )

        # Extract the file name from the GCS URI
        blob_name = gcs_uri.replace(f"gs://{bucket_name}/", "")
        blob = bucket.blob(blob_name)
        file_contents = blob.download_as_text()

        full_prompt = f"{file_contents}\n\nQuestion: {prompt}"
        response = llm.invoke(full_prompt)
        return {"response": response.text}
    except Exception as e:
        return {"error": str(e)}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Print error for logging/debugging
    print(f"Unhandled_exception: {exc}")

    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
        headers={"Access-Control-Allow-Origin": "*",  # 👈 CORS headers here
                 "Access-Control-Allow-Methods": "*",
                 "Access-Control-Allow-Headers": "*"},
    )