import os
import vertexai
from langchain_google_vertexai import ChatVertexAI
from google.cloud import storage
import fitz

bucket_name = os.environ.get("BUCKET_NAME")
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

SYSTEM_PROMPT = """You are an Invention Detection and Classification Agent. 
Your role is to determine whether a provided document describes a patent-eligible invention under United States law, specifically 35 U.S.C. § 101.

---

**Legal Reference: 35 U.S.C. § 101 - Inventions patentable**
Whoever invents or discovers any new and useful process, machine, manufacture, or composition of matter, 
or any new and useful improvement thereof, may obtain a patent therefor, subject to the conditions and requirements of this title.

---

**Overview of Your Task:**
You will analyze the provided document to assess:
1. Whether the described subject matter falls into one of the statutory categories: 
   - Process
   - Machine
   - Manufacture
   - Composition of matter
   - Improvement of the above
2. Whether it appears new and useful.
3. Whether it is excluded under judicial exceptions (e.g., laws of nature, natural phenomena, abstract ideas).

---

**Requirements:**
- Carefully read the text of the document.
- Identify explicit or implicit descriptions of processes, machines, manufactures, compositions of matter, or improvements thereof.
- Ignore irrelevant material that does not pertain to patentable subject matter.
- Apply the standard of 35 U.S.C. § 101 and flag if the document does not appear to meet the basic eligibility criteria.
- Use plain, clear language in your reasoning.
- Output strictly in JSON format — no extra text.

---

**Output format (JSON only):**
{
  "is_invention": true | false,
  "statutory_category": ["process", "machine", "manufacture", "composition of matter", "improvement"], 
  "meets_101": true | false,
  "reasoning": "Brief explanation of why it meets or fails 35 U.S.C. § 101",
  "evidence": ["Key excerpt 1", "Key excerpt 2"]
}

---
Now analyze the following document:
"""

def run_idca(gcs_uri: str) -> str:

    project_id = os.environ.get("GCP_PROJECT_ID")
    region = os.environ.get("GCP_REGION")
    vertexai.init(project=project_id, location=region)

    llm = ChatVertexAI (
        model="gemini-2.5-pro",
        temperature=0,
        max_output_tokens=4096,
    )

    blob_name = gcs_uri.replace(f"gs://{bucket_name}/", "")
    blob = bucket.blob(blob_name)
    doc_bytes = blob.download_as_bytes()

    # Extract text from the document
    with fitz.open(stream=doc_bytes, filetype="pdf") as doc:
        file_contents = ""
        for page in doc:
            file_contents += page.get_text()
    prompt = f"{SYSTEM_PROMPT}\n\n{file_contents}"

    response = llm.invoke(prompt)
    return response.text()