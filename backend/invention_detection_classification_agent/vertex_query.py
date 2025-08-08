import os
import vertexai
from langchain_google_vertexai import ChatVertexAI
from google.cloud import storage
import fitz
import re, json

bucket_name = os.environ.get("BUCKET_NAME")
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

SYSTEM_PROMPT = """You are a U.S. patent eligibility classifier.

Your job is to analyze a provided document to determine:  
1. Whether an invention is disclosed or implied.  
2. Whether it qualifies as patent-eligible subject matter under U.S. law (35 U.S.C. § 101).  
3. If eligible, how it should be classified for downstream novelty evaluation.

---

LEGAL REFERENCE: 35 U.S.C. § 101 – Inventions Patentable
"Whoever invents or discovers any new and useful process, machine, manufacture, or composition of matter, or any new and useful improvement thereof, may obtain a patent therefor, subject to the conditions and requirements of this title."

---

## STEP-BY-STEP DECISION LOGIC

### 1. Detect Invention Presence
- Question: Does this document describe a **technical solution to a technical problem** in sufficient detail to support a patent claim?
    - If **NO**:
        - Ask: Is an invention **implied** or **absent**?
            - *Implied*: Document contains indicators such as performance data but lacks implementation detail.
            - *Absent*: No technical solution is described or implied.
        - **Terminate** with:
        ```json
        {
          "invention_status": "implied" | "absent",
          "termination_reason": "no invention detected"
        }
        ```

### 2. Check Subject Matter Eligibility (35 U.S.C. § 101)
- If invention is **present**, ask:
    - Does it fall into at least one statutory category?:
        - process
        - machine
        - manufacture
        - composition of matter
    - If it falls entirely within a **judicial exception** (abstract idea, law of nature, natural phenomenon) and lacks an inventive concept that transforms it into a patent-eligible application, mark it as ineligible.
        - **Terminate** with:
        ```json
        {
          "invention_status": "present",
          "subject_matter_eligibility": "ineligible",
          "termination_reason": "fails 35 USC § 101"
        }
        ```

### 3. Classify the Invention (only if invention is present and eligible)
- Internally generate a **minimal summary** to support classification.
- Identify:
    - `"invention_type"`: e.g., method, system, composition, device
    - `"technical_fields"`: e.g., robotics, chemistry, software
    - `"CPC_section"` *(optional)*: e.g., B, G, H
- **Final Output**:
```json
{
  "invention_status": "present",
  "subject_matter_eligibility": "eligible",
  "invention_type": "...",
  "technical_fields": ["..."],
  "CPC_section": "...",
}
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

    response_text = llm.invoke(prompt).text()

    cleaned_text = re.sub(r"^```json\s*|\s*```$", "", response_text.strip(), flags=re.MULTILINE)
    try:
        # Convert to dict so FastAPI will return proper JSON
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError:
        # If parsing fails, just return the cleaned string
        parsed = {"raw_response": cleaned_text}
    return parsed