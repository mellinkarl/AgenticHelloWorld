"""
This program serves as an example of how AMIE can utilize tools in an MVP

    1. Accept and process a file upload via a POST request

    2. Stream the file to GCS Bucket (without storing it in memory)

    3. Prompt Gemini LLM:
        a. With text and file content
        b. Enforcing an output format (schema)
        c. In the background (allows to return request id to user immediately)

    4. Allow user to make status checks and return result
"""

from fastapi import FastAPI, UploadFile, File, Query, HTTPException, BackgroundTasks
from uuid import uuid4, UUID
import json
from google.cloud import storage
from google import genai
from google.genai import types
from typing import Literal

"""
Locally, connects through Application Default Credentials (ADC) through gcloud CLI : "gcloud auth application-default login" in ~/.config/gcloud/application_default_credentials.json

When running in Google Cloud, credentials are automatically pulled from the metadata server, from service account attached
"""
storage_client = storage.Client()
genai_client = genai.Client(vertexai=True, project="aime-hello-world", location="us-west1")

# Connect to manuscripts bucket
bucket = storage_client.bucket("aime-manuscripts")


app = FastAPI()


# Object to store manuscript data
class Manuscript():
    def __init__(self, file_name, content_type, bucket_name):
        self.request_id: UUID = uuid4()
        self.filename: str = file_name
        self.objectname: str = f"{self.request_id}_{self.filename}"
        self.type: str = content_type
        self.gcs_uri: str = f"gs://{bucket_name}/{self.objectname}"
        self.finished: bool = False
        self.status: Literal["PENDING", "WORKING", "FAILED", "SUCCESS"] = "PENDING" # Lifecycle: PENDING -> WORKING -> SUCCESS/FAILED
        self.response: str = ""


# Store requests as id:manuscript
files: dict[UUID, Manuscript] = {}


@app.get("/")
def root():
    """Health check."""
    return {"status": "active"}

# Check status of request. Returns status if not d
@app.get("/status")
async def request_status(id: UUID = Query(...)):
    """
    Get status of a manuscript.
    - When SUCCESS: returns {"response": <JSON result>}
    - Else: returns {"response": "PENDING"/"WORKING"/"FAILED"}.
    """

    m = files.get(id)

    if m is None:
        raise HTTPException(404, detail="ID not found")

    if m.status == "SUCCESS":
        return {"response": m.response}

    return {"response": m.status}
    

@app.post("/invoke")
async def new_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Accept a file upload, upload it to GCS, and immediately start a background
    Gemini analysis. Returns a request ID that clients can use with /status.
    """
    
    # Create record now so clients can query /status immediately.
    m = Manuscript(file.filename, file.content_type, bucket.name)
    files[m.request_id] = m

    # Upload file to Google Cloud Bucket.
    await upload_to_cloud(file, m)

    # Enque LLM call to run in background: can return request id right away
    background_tasks.add_task(prompt_vertex, m)

    return {"id": m.request_id}


async def upload_to_cloud(file: UploadFile, m: Manuscript):

    new_blob = bucket.blob(m.objectname)

    file.file.seek(0)
    # Stream from FastAPI file object to GCS Bucket
    new_blob.upload_from_file(
        file.file,
        rewind=True,
        content_type=file.content_type
    )

    await file.close()
    print(f"File uploaded to {m.gcs_uri}, type: {m.type}")


def prompt_vertex(m: Manuscript):

    m.status = "WORKING"

    if not m.type == "application/pdf":
        m.status = "FAILED"
        m.finished = True
        return
    
    try:

        resp = genai_client.models.generate_content(
            model="gemini-2.0-flash-lite-001",
            contents=[
                types.Part.from_uri(file_uri=m.gcs_uri, mime_type="application/pdf"),
                "Analyze the file attached"
            ],
            config=types.GenerateContentConfig(
                system_instruction="You are a patent reviewer. Attached is a manuscript, and your job is to: DETERMINE WHAT INVENTION IS SOUGHT TO BE PATENTED: (1) Identify and Understand Any Utility for the Invention, The claimed invention as a whole must be useful. The purpose of this requirement is to limit patent protection to inventions that possess a certain level of “real world” value, as opposed to subject matter that represents nothing more than an idea or concept, or is simply a starting point for future investigation or research; (2) Review the Detailed Disclosure and Specific Embodiments of the Invention To Understand What the Applicant Has Asserted as the Invention, The written description will provide the clearest explanation of the invention, by exemplifying the invention, explaining how it relates to the prior art and explaining the relative significance of various features of the invention; (3) Review the Claims, When performing claim analysis, examine each claim as a whole, giving it the broadest reasonable interpretation in light of the specification. Identify and evaluate every limitation—steps for processes, structures/materials for products—and correlate them with the disclosure. Consider grammar and plain meaning, but remember optional or intended-use language may not limit scope. Do not import limitations from the specification into the claim, and always interpret means/step-plus-function terms with their disclosed structures and equivalents. Return only JSON file with the title of the manuscript, the authors, whether an invention is present, implied, or absent, and if present or implied, provide a summary.",
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "authors": {"type": "array", "items": {"type": "string"}},
                        "status": {"type": "string", "enum": ["present", "implied", "absent"]},
                        "summary": {"type": "string"}
                    },
                    "required": ["title", "authors", "status", "summary"]
                }
            ),
        )

        text = resp.text
        m.response = json.loads(text)
        m.status = "SUCCESS"
        m.finished = True
        print("finished LLM")
        return
    
    except Exception as e:
        m.status = "FAILED"
        m.finished = True

        return
