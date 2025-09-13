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
    # NOTE: No literal { } braces here to avoid str.format conflicts.
    # The JSON object shape is enforced by the response schema instead.
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

    # For future: innovation type recognition
    # {0} -> summary, {1} -> taxonomy text
    # (braces are escaped here so str.format doesn't treat them as placeholders)
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
