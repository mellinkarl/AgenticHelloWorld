# amie/agents/prompt/naa_prompt.py
# Minimal prompt loader with positional formatting + shared system headers
# Author: Harry
# 2025-09-12

from typing import Dict

# -----------------------
# Template keys
# -----------------------
TPL_CPC_L1 = "cpc_l1"
TPL_CPC_L2 = "cpc_l2"
TPL_INNOVATION_TYPE = "innovation_type"  # for future use

# Detail extraction templates (one per InnovationType)
TPL_DETAIL_METHOD = "detail_method"
TPL_DETAIL_MACHINE = "detail_machine"
TPL_DETAIL_MANUFACTURE = "detail_manufacture"
TPL_DETAIL_COMPOSITION = "detail_composition"
TPL_DETAIL_DESIGN = "detail_design"

_TEMPLATES: Dict[str, str] = {
    # {0} -> summary, {1} -> CPC Level-1 human-readable string
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

    # {0} -> summary, {1} -> concatenated Level-2 options string for chosen Level-1 sections
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

    # {0} -> summary, {1} -> taxonomy text
    TPL_INNOVATION_TYPE: (
        "### TASK\n"
        "Classify the invention into one of the patentable subject-matter categories.\n\n"
        "### INPUT: SUMMARY\n"
        "{0}\n\n"
        "### CATEGORY TAXONOMY (authoritative)\n"
        "{1}\n\n"
        "### OUTPUT\n"
        "Return ONLY a JSON object: {{\"invention_type\": \"process|machine|manufacture|composition|design|none\"}}.\n"
    ),

    # -----------------------
    # Detail extraction templates
    # Each uses: {0}=summary, {1}=type_name, {2}=type_description, {3}=doc_uri (may be empty).
    # -----------------------

    TPL_DETAIL_METHOD: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Goal: extract deterministic, structured method details.\n"
        "- Output MUST be valid JSON matching the requested schema.\n"
        "- Use ONLY the provided inputs (PDF + text). If uncertain, return minimal fields.\n\n"
        "### TASK\n"
        "The invention type is: {1}.\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty):\n{3}\n\n"
        "### REQUIRED OUTPUT SHAPE\n"
        "Return ONLY a JSON object matching the schema fields:\n"
        "- method_steps: array[string] (chronological, concrete, executable steps)\n"
        "- assumptions: array[string]\n"
        "- constraints: array[string]\n"
        "Be concise, do not invent facts, and prefer quoting terminology from the PDF when unambiguous.\n"
    ),

    TPL_DETAIL_MACHINE: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Goal: extract deterministic, structured machine details.\n"
        "- Output MUST be valid JSON matching the requested schema.\n"
        "- Use ONLY the provided inputs (PDF + text). If uncertain, return minimal fields.\n\n"
        "### TASK\n"
        "The invention type is: {1}.\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty):\n{3}\n\n"
        "### REQUIRED OUTPUT SHAPE\n"
        "Return ONLY a JSON object with fields:\n"
        "- components: array[object{{name, function, key_specs}}]\n"
        "- subsystems: array[string]\n"
        "- connections: array[string]  # how parts interface (mechanical/electrical/data)\n"
        "- operating_principles: array[string]\n"
        "- materials: array[string]\n"
        "- sensors_actuators: array[string]\n"
        "- constraints: array[string]\n"
        "Be specific about physical structure and interfaces.\n"
    ),

    TPL_DETAIL_MANUFACTURE: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Goal: extract deterministic details for an article of manufacture.\n"
        "- Output MUST be valid JSON matching the requested schema.\n"
        "- Use ONLY the provided inputs (PDF + text). If uncertain, return minimal fields.\n\n"
        "### TASK\n"
        "The invention type is: {1}.\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty):\n{3}\n\n"
        "### REQUIRED OUTPUT SHAPE\n"
        "Return ONLY a JSON object with fields:\n"
        "- article_components: array[object{{name, function}}]\n"
        "- materials: array[string]\n"
        "- dimensions: array[string]\n"
        "- manufacturing_steps: array[string]\n"
        "- assembly: array[string]\n"
        "- tolerances: array[string]\n"
        "Focus on the physical article and its fabrication.\n"
    ),

    TPL_DETAIL_COMPOSITION: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Goal: extract deterministic details for a composition of matter.\n"
        "- Output MUST be valid JSON matching the requested schema.\n"
        "- Use ONLY the provided inputs (PDF + text). If uncertain, return minimal fields.\n\n"
        "### TASK\n"
        "The invention type is: {1}.\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty):\n{3}\n\n"
        "### REQUIRED OUTPUT SHAPE\n"
        "Return ONLY a JSON object with fields:\n"
        "- constituents: array[object{{name, role, amount}}]  # amount can be ranges/percentages\n"
        "- synthesis_steps: array[string]\n"
        "- properties: array[string]\n"
        "- use_cases: array[string]\n"
        "- constraints: array[string]\n"
        "Report quantitative details only if present; otherwise omit or be qualitative.\n"
    ),

    TPL_DETAIL_DESIGN: (
        "### SYSTEM\n"
        "- You are a senior patent analyst.\n"
        "- Goal: extract deterministic details for an ornamental design (design patent).\n"
        "- Output MUST be valid JSON matching the requested schema.\n"
        "- Use ONLY the provided inputs (PDF + text). If uncertain, return minimal fields.\n\n"
        "### TASK\n"
        "The invention type is: {1}.\n"
        "Type description:\n{2}\n\n"
        "### INPUTS\n"
        "Short summary:\n{0}\n\n"
        "If available, a PDF is attached via URI (may be empty):\n{3}\n\n"
        "### REQUIRED OUTPUT SHAPE\n"
        "Return ONLY a JSON object with fields:\n"
        "- ornamental_features: array[string]\n"
        "- views: array[string]  # referenced figures or views, e.g., front, top, perspective\n"
        "- non_functional_statement: string  # confirm ornamental focus\n"
        "- claim_scope_note: string  # concise verbal summary of the ornamental claim\n"
        "Do not speculate about utility; confine to ornamental aspects.\n"
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
def build_prompt(template_key: str, *args) -> str:
    """
    Load a task template by key and format it with positional args.
    The caller controls what to pass in (order-sensitive).
    NOTE: Any literal curly braces in templates must be doubled: '{{' and '}}'.
    """
    if template_key not in _TEMPLATES:
        raise KeyError(f"Unknown template_key: {template_key}")
    return _TEMPLATES[template_key].format(*args)


def build_prompt_sys(system_key: str, template_key: str, *args) -> str:
    """
    Prepend a shared system header, then append the formatted task prompt.
    """
    if system_key not in _SYSTEMS:
        raise KeyError(f"Unknown system_key: {system_key}")
    return _SYSTEMS[system_key] + "\n" + build_prompt(template_key, *args)


# -----------------------
# Utility (for future prompts)
# -----------------------
def format_innovation_taxonomy_text(descriptions: Dict[str, str]) -> str:
    """
    Turn an InnovationType description dict into a readable block for prompts.
    """
    return "\n".join(f"- {k}: {v}" for k, v in descriptions.items())
