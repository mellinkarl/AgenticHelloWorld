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

# ----------------- Dummy Present Version -----------------

def idca_node_dummy(state: GraphState, config=None) -> Dict[str, Any]:
    """
    Invention Detection & Classification Agent (mock, always 'present'):
    - Returns a fixed example output for testing downstream agents (NAA/AA).
    - Does not call LLM.
    """
    print("[IDCA][DUMMY] Returning fixed 'present' mock output")

    # Mock Step1: metadata + fields
    step1 = {
        "title": "Strong, Accurate, and Low-Cost Robot Manipulator",
        "authors": [
            "Georges Chebly",
            "Spencer Little",
            "Nisal Perera",
            "Aliya Abedeen",
            "Ken Suzuki",
            "Donghyun Kim"
        ],
        "manuscript_type": "research paper",
        "fields_needed": ["Robotics", "Mechanical Design", "3D Printing", "Control Systems", "Education"],
    }

    # Mock Step2: invention classification (always present)
    step2 = {
        "patent_type": "product",
        "status": "present",
        "reasoning": (
            "The manuscript describes a concrete product—a 3D-printable 6-DoF robotic arm (Forte) "
            "featuring a capstan-based cable drive, belt-cable hybrid transmission, and optimized "
            "3D-printed structures. These are specific technical implementations with clear novelty."
        ),
    }

    # Mock Step3: summary (technical detail for semantic search)
    step3 = {
        "summary": (
            "Forte is a fully 3D-printed, 6-DoF robotic manipulator designed to deliver near industrial-"
            "grade precision (0.467 mm repeatability) and payload capacity (0.63 kg) at a material cost "
            "under $215. Key innovations include: a capstan-based cable drive for low backlash and high "
            "torque efficiency; a belt-cable hybrid transmission for shoulder and elbow joints; vented "
            "screw tensioning for easy assembly; and topology-optimized PLA structures for stiffness "
            "and lightweight performance. Three motors at the elbow reduce torque load, enabling "
            "competitive performance for robotics education and research at low cost."
        )
    }

    idca_art = {
        **step1,
        **step2,
        **step3,
    }

    idca_cache = {
        "model_version": "idca-dummy-present-v1",
    }

    return {
        "artifacts": {"idca": idca_art},
        "internals": {"idca": idca_cache},
        "runtime": {"idca": {"status": "FINISHED", "route": []}},
        "logs": ["[IDCA][DUMMY] Emitted fixed 'present' output"],
    }

def call_LLM(genai_client: genai.Client, model_name: str, content: types.ContentListUnionDict, conf: types.GenerateContentConfigOrDict | None = None) -> dict | None:
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
    step1_prompt="Read this manuscript. Determine the title, the author, and determine what fields are needed to understand this manuscript."
    step1_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "authors": {"type": "array", "items": {"type": "string"}},
                        "manuscript_type": {"type": "string"},
                        "fields_needed": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["title", "authors", "manuscript_type", "fields_needed"]
                }
    step1 = None
    for i in range(5):
        step1 = call_LLM(genai_client, model_name=model, content=multimedia_content(step1_prompt, src), conf=response_schema(step1_schema))
        if step1 is not None:
            break
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
                        "patent_type": {"type": "string", "enum": ["process", "product", "both", "unknown"]},
                        "status": {"type": "string", "enum": ["present", "implied", "absent"]},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["patent_type", "status", "reasoning"]
                }
    step2 = None
    for i in range(5):
        step2 = call_LLM(genai_client, model_name=model, content=multimedia_content(step2_prompt, src), conf=response_schema(step2_schema))
        if step2 is not None:
            break
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
    step3 = None
    for i in range(5):
        step3 = call_LLM(genai_client, model_name=model, content=multimedia_content(step3_prompt, src), conf=response_schema(step3_schema))
        if step3 is not None:
            break
    if step3 is None:
        return generate_output("LLM malfunctioned in step 3", step1, step2)
    print(f"third llm call, response: {step3}")



    return generate_output("Invention detected", step1, step2, step3)

INVENTION_D_C = RunnableLambda(idca_node_dummy)

