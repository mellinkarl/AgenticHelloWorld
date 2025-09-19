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
TPL_INNOVATION_TYPE = "innovation_type"

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
    # IMPORTANT: Schema stays the same; we only make the content more explicit/detailed.
    # -----------------------

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
        "- method_steps: array[string] — ordered, actionable steps with numbered prefixes, e.g., \"1) Acquire signal ...\".\n"
        "- assumptions: array[string]\n"
        "- constraints: array[string]\n"
        "Be chronological and specific; avoid vague phrasing.\n"
    ),

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
        "- components: array[object{{name, function, key_specs}}] — be granular; keep model numbers and key ratios in key_specs.\n"
        "- subsystems: array[string] — system-level groupings (e.g., \"Cable drive system\").\n"
        "- connections: array[string] — **explicit edges** in the form:\n"
        "  \"order N: [FROM] -> [TO] via [INTERFACE/MEDIUM]; materials=[MATERIAL SPEC]; notes=[ROUTING/FASTENER/GEAR TYPE]\".\n"
        "  Examples: \"order 1: Stepper motor (NEMA 17) -> Capstan drive via steel cable; materials=steel cable 7x7 1.2mm, PTFE-coated; notes=preload 30N, routed through idler pulleys P1,P2\".\n"
        "  \"order 2: Capstan drive -> Elbow pulley via timing belt; materials=GT3 5MGT-9; notes=tension 40N\".\n"
        "- operating_principles: array[string] — e.g., \"Cable-driven transmission\", \"Topology optimization for stiffness\".\n"
        "- materials: array[string] — include detailed specs, e.g., \"Steel cable 7x7, 1.2 mm, pre-stretched\".\n"
        "- sensors_actuators: array[string] — e.g., \"Stepper motors (NEMA 17, NEMA 23)\".\n"
        "- constraints: array[string] — numeric targets preferred, e.g., \"Cost under $215\", \"0.63 kg payload\".\n"
        "Keep `connections` strictly as strings but **always** include from/to, interface/medium, order, and material notes (steel cable specs if present).\n"
    ),

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
        "- article_components: array[object{{name, function}}] — granular parts list.\n"
        "- materials: array[string] — include grades/specs (e.g., \"6061-T6\"), surface finishes, or cable specs if relevant.\n"
        "- dimensions: array[string] — include units.\n"
        "- manufacturing_steps: array[string] — ordered, numbered.\n"
        "- assembly: array[string] — ordered, numbered, with joining methods.\n"
        "- tolerances: array[string]\n"
    ),

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
        "- constituents: array[object{{name, role, amount}}] — amounts may be ranges/percentages.\n"
        "- synthesis_steps: array[string] — ordered, numbered.\n"
        "- properties: array[string]\n"
        "- use_cases: array[string]\n"
        "- constraints: array[string]\n"
    ),

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
        "- views: array[string] — reference figure names or viewpoints.\n"
        "- non_functional_statement: string\n"
        "- claim_scope_note: string\n"
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
    if template_key not in _TEMPLATES:
        raise KeyError(f"Unknown template_key: {template_key}")
    return _TEMPLATES[template_key].format(*args)


def build_prompt_sys(system_key: str, template_key: str, *args) -> str:
    if system_key not in _SYSTEMS:
        raise KeyError(f"Unknown system_key: {system_key}")
    return _SYSTEMS[system_key] + "\n" + build_prompt(template_key, *args)


def format_innovation_taxonomy_text(descriptions: Dict[str, str]) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in descriptions.items())
