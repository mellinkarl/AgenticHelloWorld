# amie/agents/idca_agent.py
# Invention Detection & Classification Agent
# Author: Harry
# 2025-08-18

import json
from typing import Dict, Any
from langchain_core.runnables import RunnableLambda
from google import genai
from google.genai import types
from ..state import GraphState

model = "gemini-2.0-flash-lite-001"

def call_LLM(genai_client: genai.Client, model_name: str, content: types.ContentListUnionDict, conf: types.GenerateContentConfigOrDict | None = None, repeats = 5) -> dict | None:
    
    for i in range(repeats):

        output = None

        try:    

        resp = genai_client.models.generate_content(
            model=model_name,
            contents=content,
            config=conf
        )

        text = resp.text
        return json.loads(text)

    except Exception as e:
        print(f"LLM error: {e}")
        return None
    
def multimedia_content(prompt: str,uri: str, m_type: str = "application/pdf") -> list:
    return [types.Part.from_uri(file_uri=uri, mime_type=m_type), prompt]

def response_schema(schema = dict, response_type: str = "application/json") -> types.GenerateContentConfig:
    return types.GenerateContentConfig(response_schema=schema, response_mime_type=response_type)


def generate_output(log: str, step1: dict | None = None, step2: dict | None = None, step3: dict | None = None) -> dict:

    artifacts = {}
    cache = {}

    artifacts["status"] = "absent"

    if step1:
        artifacts["publish_date"] = step1["publish_date"]
        artifacts["fields"] = step1["fields_needed"]
        artifacts["manuscript_type"] = step1["manuscript_type"]
        cache["title"] = step1["title"]
        cache["authors"] = step1["authors"]

    if step2:
        artifacts["status"] = step2["status"]
        artifacts["reasoning"] = step2["reasoning"]
        cache["patent_type"] = step2["patent_type"]

    if step3:
        artifacts["summary"] = step3["summary"]

    return {
        "runtime":   {"idca": {"status": "FINISHED", "route": []}},
        "artifacts": {"idca": artifacts},
        "internals": {"idca": cache},
        "logs": [log]
    }




def idca_node(state: GraphState, config) -> Dict[str, Any]:
    """
    Invention Detection & Classification Agent (dummy):
    - Reads IA internals (normalized_uri) just to demonstrate cross-agent read.
    - Emits a tiny 'idca' artifact.
    """
    print("start idca")

    ia_cache = (state.get("internals") or {}).get("ia") or {}
    src = state.get("doc_gcs_uri")
    genai_client = config["configurable"]["genai_client"]

    assert genai_client is not None, "genai_client missing in config['configurable']"
    assert isinstance(genai_client, genai.Client), f"genai_client wrong type: {type(genai_client)}"

    """
    Step 1 - Classify Manuscript:
    - Determine what type of manuscript it is.
    - Determine fields needed to understand manuscript
    """
    step1_prompt="Read this manuscript. Determine the title, the author, the publish date, and determine what fields are needed to understand the subject matter of this manuscript. If you cannot find the publish date, or are not sure if the date found is the true publish date or something else, make publish_date null, otherwise, make publish_date the date found in RFC 3339, section 5.6 format "
    step1_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "authors": {"type": "array", "items": {"type": "string"}},
                        "publish_date": {"type": ["string", "null"], "format": "date", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
                        "manuscript_type": {"type": "string"},
                        "fields_needed": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["title", "authors", "manuscript_type", "fields_needed"]
                }
    
    step1 = call_LLM(genai_client, model_name=model, content=multimedia_content(step1_prompt, src), conf=response_schema(step1_schema))
    if step1 is None:
        return generate_output("LLM malfunctioned in step 1")
    print(f"first llm call, response: {step1}")

    """
    Step 2 - Identify Invention:
    - Determine if an invention is = Present | Implied | Absent
    """
    step2_prompt = f"You are a patent reviewer responsible for assessing from the following paper, what type of paper this is (research paper, patent application, resume, etc), and if the potential patent is describing a = process | product | both | unknown, and if an invention is = present | implied | absent. Attached is a manuscript, and your job is to: DETERMINE WHAT INVENTION IS SOUGHT TO BE PATENTED: (1) Identify and Understand Any Utility for the Invention, The claimed invention as a whole must be useful. The purpose of this requirement is to limit patent protection to inventions that possess a certain level of “real world” value, as opposed to subject matter that represents nothing more than an idea or concept, or is simply a starting point for future investigation or research; (2) Review the Detailed Disclosure and Specific Embodiments of the Invention To Understand What the Applicant Has Asserted as the Invention, The written description will provide the clearest explanation of the invention, by exemplifying the invention, explaining how it relates to the prior art and explaining the relative significance of various features of the invention; (3) Review the Claims, When performing claim analysis, examine each claim as a whole, giving it the broadest reasonable interpretation in light of the specification. Identify and evaluate every limitation—steps for processes, structures/materials for products—and correlate them with the disclosure. Consider grammar and plain meaning, but remember optional or intended-use language may not limit scope. Do not import limitations from the specification into the claim, and always interpret means/step-plus-function terms with their disclosed structures and equivalents. Finally, provide reasoning for your decision. Output in a JSON format strictly, with only the fields 'patent_type': 'process': Literal('process', 'product', 'both', 'unknown') 'status': Literal('present', 'implied', 'absent') and 'reasoning': str"
    step2_schema={
                    "type": "object",
                    "properties": {
                        "patent_type": {"type": "string", "enum": ["method", "apparatus", "both", "unknown"]},
                        "status": {"type": "string", "enum": ["present", "implied", "absent"]},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["patent_type", "status", "reasoning"]
                }

    step2 = call_LLM(genai_client, model_name=model, content=multimedia_content(step2_prompt, src), conf=response_schema(step2_schema))
    if step2 is None:
        return generate_output("LLM malfunctioned in step 2", step1)
    print(f"second llm call, response: {step2}")

    """
    Step 3 - Summarize:
    - If invention is present, summarize in natural language
    """
    if step2["status"] != "present":
        # No invention, skip summary and jump to AA
        return generate_output("Invention is not present", step1, step2)

    step3_prompt = "You are preparing text to be used for vector embeddings in a patent novelty search. From the following manuscript or patent document, generate a compact technical summary of the invention suitable for semantic search. The summary should: Clearly state what the invention is (object, system, or method), List the essential technical features and constraints (materials, dimensions, conditions, ranges, negative limitations), Include the functional purpose (what problem it solves or effect it achieves), Use concise technical natural language (avoid boilerplate like “the present invention relates to”), Normalize units and terminology (e.g., “5 °C” not “five degrees Celsius”), limit to 200-300 words, no filler sentences"
    step3_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"}
                    },
                    "required": ["summary"]
                }

    step3 = call_LLM(genai_client, model_name=model, content=multimedia_content(step3_prompt, src), conf=response_schema(step3_schema))
    if step3 is None:
        return generate_output("LLM malfunctioned in step 3", step1, step2)
    print(f"third llm call, response: {step3}")

    return generate_output("Invention detected", step1, step2, step3)

INVENTION_D_C = RunnableLambda(idca_node_dummy)

