# amie/agents/prompt/naa_prompt.py
# Minimal prompt loader with positional formatting + shared system headers
# Author: Harry
# 2025-09-23

from typing import Dict

# -----------------------
# Template keys
# -----------------------
TPL_CPC_L1 = "cpc_l1"
TPL_CPC_L2 = "cpc_l2"
TPL_INNOVATION_TYPE = "innovation_type"

# Detail extraction templates
TPL_DETAIL_METHOD = "detail_method"
TPL_DETAIL_MACHINE = "detail_machine"
TPL_DETAIL_MANUFACTURE = "detail_manufacture"
TPL_DETAIL_COMPOSITION = "detail_composition"
TPL_DETAIL_DESIGN = "detail_design"

# Enumerate novelty aspects
TPL_NOVELTY_ASPECTS = "novelty_aspects"

# Single Google Scholar query (generic; no arXiv restriction)
TPL_SCHOLAR_SINGLE_QUERY = "scholar_single_query"

# PDF vs PDF comparison (retained for future use)
TPL_COMPARE_PDFS = (
    "### SYSTEM\n"
    "- You are a senior patent analyst.\n"
    "- Compare ONLY the two attached PDFs (first is the invention, second is the candidate reference).\n"
    "- Ignore titles, authors, years, venues; judge from content only.\n"
    "- Output MUST be valid JSON exactly matching the schema.\n"
    "- If an item is uncertain, omit it; do not hallucinate.\n\n"
    "### TASK\n"
    "1) List concise bullets of OVERLAP (already present in both PDFs).\n"
    "2) List concise bullets of NOVELTY (present in invention, absent in candidate).\n"
    "3) Give an overall SIMILARITY percentage [0..100], where 100 means the candidate fully discloses the same.\n\n"
    "### OUTPUT (STRICT)\n"
    "{\"overlap\": [\"...\"], \"novelty\": [\"...\"], \"similarity\": 0.0}\n"
)

_TEMPLATES: Dict[str, str] = {
    # CPC L1
    TPL_CPC_L1: (
        "### TASK\n"
        "Decide which CPC Level-1 section(s) the invention belongs to.\n\n"
        "### INPUT: SUMMARY\n"
        "{0}\n\n"
        "### INPUT: CPC LEVEL-1 OPTIONS (authoritative)\n"
        "{1}\n\n"
        "### OUTPUT\n"
        "Return ONLY a JSON array of strings with Level-1 codes (e.g., [\"A\",\"H\"]).\n"
        "If uncertain, return an empty list [].\n"
    ),
    # CPC L2
    TPL_CPC_L2: (
        "### TASK\n"
        "From the provided CPC Level-2 options, select all classes that apply to the invention.\n\n"
        "### INPUT: SUMMARY\n"
        "{0}\n\n"
        "### INPUT: CPC LEVEL-2 OPTIONS (only within previously selected Level-1 sections)\n"
        "{1}\n\n"
        "### OUTPUT\n"
        "Return ONLY a JSON object mapping class codes to their official titles.\n"
        "If uncertain, return an empty object.\n"
    ),
    # Innovation type
    TPL_INNOVATION_TYPE: (
        "### TASK\n"
        "Classify the invention into one of the patentable subject-matter categories.\n\n"
        "### INPUT: SUMMARY\n"
        "{0}\n\n"
        "### CATEGORY TAXONOMY (authoritative)\n"
        "{1}\n\n"
        "### OUTPUT\n"
        "Return ONLY a JSON object: {\"invention_type\": \"process|machine|manufacture|composition|design|none\"}.\n"
    ),

    # Detail extraction — method
    TPL_DETAIL_METHOD: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Output MUST be valid JSON per schema; do not add extra keys.\n"
        "- Use ONLY the provided inputs (PDF + text). If any field is unknown, return an empty array for it.\n\n"
        "### TASK\n"
        "The invention type is: {1}\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty): {3}\n\n"
        "### REQUIRED OUTPUT SHAPE (schema-preserving)\n"
        "- method_steps: array[string] — numbered, granular, covering ALL stages (inputs, processing, outputs).\n"
        "- assumptions: array[string]\n"
        "- constraints: array[string] — include numeric targets if present.\n"
        "Be chronological, exhaustive, and do not invent steps.\n"
    ),
    # machine
    TPL_DETAIL_MACHINE: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Output MUST be valid JSON per schema; do not add extra keys.\n"
        "- Use ONLY the provided inputs (PDF + text). If any field is unknown, return an empty array for it.\n\n"
        "### TASK\n"
        "The invention type is: {1}\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty): {3}\n\n"
        "### REQUIRED OUTPUT SHAPE (schema-preserving)\n"
        "- components: array[object{{name, function, key_specs}}]\n"
        "- subsystems: array[string]\n"
        "- connections: array[string] — explicit interfaces.\n"
        "- operating_principles: array[string]\n"
        "- materials: array[string]\n"
        "- sensors_actuators: array[string]\n"
        "- constraints: array[string]\n"
        "Aim for exhaustive coverage of physical structure and interfaces.\n"
    ),
    # manufacture
    TPL_DETAIL_MANUFACTURE: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Output MUST be valid JSON per schema; do not add extra keys.\n"
        "- Use ONLY the provided inputs (PDF + text). If any field is unknown, return an empty array for it.\n\n"
        "### TASK\n"
        "The invention type is: {1}\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty): {3}\n\n"
        "### REQUIRED OUTPUT SHAPE (schema-preserving)\n"
        "- article_components: array[object{{name, function}}]\n"
        "- materials: array[string]\n"
        "- dimensions: array[string]\n"
        "- manufacturing_steps: array[string]\n"
        "- assembly: array[string]\n"
        "- tolerances: array[string]\n"
        "Be complete across fabrication and assembly.\n"
    ),
    # composition
    TPL_DETAIL_COMPOSITION: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Output MUST be valid JSON per schema; do not add extra keys.\n"
        "- Use ONLY the provided inputs (PDF + text). If any field is unknown, return an empty array for it.\n\n"
        "### TASK\n"
        "The invention type is: {1}\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty): {3}\n\n"
        "### REQUIRED OUTPUT SHAPE (schema-preserving)\n"
        "- constituents: array[object{{name, role, amount}}]\n"
        "- synthesis_steps: array[string]\n"
        "- properties: array[string]\n"
        "- use_cases: array[string]\n"
        "- constraints: array[string]\n"
        "Cover all material facets that are present.\n"
    ),
    # design
    TPL_DETAIL_DESIGN: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Output MUST be valid JSON per schema; do not add extra keys.\n"
        "- Use ONLY the provided inputs (PDF + text). If any field is unknown, return an empty array for it.\n\n"
        "### TASK\n"
        "The invention type is: {1}\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty): {3}\n\n"
        "### REQUIRED OUTPUT SHAPE (schema-preserving)\n"
        "- ornamental_features: array[string]\n"
        "- views: array[string]\n"
        "- non_functional_statement: string\n"
        "- claim_scope_note: string\n"
    ),

    # Enumerate ALL novelty aspects
    TPL_NOVELTY_ASPECTS: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Output MUST be valid JSON matching the schema exactly.\n\n"
        "### TASK\n"
        "From the provided invention details, enumerate ALL potential novelty aspects across:\n"
        "mechanisms/approaches, components, materials, control/algorithms, geometry/topology, constraints/targets,\n"
        "and applications. Use concise aspect labels (5–10 words each). Deduplicate.\n"
        "Target 12–30 aspects if information allows.\n\n"
        "### INPUTS\n"
        "Invention type: {1}\n"
        "Summary:\n{2}\n\n"
        "Details JSON:\n{0}\n\n"
        "### OUTPUT (STRICT)\n"
        "{\"aspects\": [\"<aspect 1>\", \"<aspect 2>\", ...]}\n"
    ),

    # Single Scholar query (generic; PDF optional; no site constraint)
    # {0}=invention_type, {1}=summary, {2}=aspects (bullets)
    TPL_SCHOLAR_SINGLE_QUERY: (
        "### SYSTEM\n"
        "- You are a literature search specialist.\n"
        "- Produce ONE relevant Google Scholar query string to retrieve core literature about the invention.\n"
        "- REQUIREMENTS:\n"
        "  * Avoid site/domain restrictions; the query should be broadly useful.\n"
        "  * Include 1–2 core domain phrases from the invention + 2–4 aspect terms (OR groups allowed).\n"
        "  * Keep under 180 chars. Avoid NOT/wildcards.\n"
        "- Output MUST be valid JSON with a single field `query`.\n\n"
        "### INPUTS\n"
        "Invention type: {0}\n"
        "Summary:\n{1}\n\n"
        "Candidate aspects:\n{2}\n\n"
        "### OUTPUT (STRICT)\n"
        "{\"query\": \"<single scholar query>\"}\n"
    ),
}

# -----------------------
# Shared system headers
# -----------------------
SYS_PATENT_CLASSIFIER = "sys_patent_classifier"
SYS_MINIMAL = "sys_minimal"

_SYSTEMS: Dict[str, str] = {
    SYS_PATENT_CLASSIFIER: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Goal: perform deterministic classification/extraction only.\n"
        "- Use ONLY the provided inputs.\n"
        "- Output MUST be valid JSON matching the requested format.\n"
        "- If uncertain, return empty lists/fields rather than guessing.\n"
    ),
    SYS_MINIMAL: (
        "### SYSTEM\n"
        "- Be concise and deterministic.\n"
        "- Output JSON only.\n"
    ),
}

# -----------------------
# Builders
# -----------------------
def _positional_sub(template: str, *args) -> str:
    out = template
    for i in sorted(range(len(args)), key=lambda x: -len(str(x))):
        out = out.replace("{" + str(i) + "}", str(args[i]))
    return out


def build_prompt(template_key: str, *args) -> str:
    if template_key not in _TEMPLATES:
        raise KeyError(f"Unknown template_key: {template_key}")
    return _positional_sub(_TEMPLATES[template_key], *args)


def build_prompt_sys(system_key: str, template_key: str, *args) -> str:
    if system_key not in _SYSTEMS:
        raise KeyError(f"Unknown system_key: {system_key}")
    combined = _SYSTEMS[system_key] + "\n" + _TEMPLATES[template_key]
    return _positional_sub(combined, *args)


def format_innovation_taxonomy_text(descriptions: Dict[str, str]) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in descriptions.items())
