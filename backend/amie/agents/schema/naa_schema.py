# amie/agents/schema/naa_schema.py
# Schemas for NAA
# Author: Harry
# 2025-09-12

from typing import Dict, Any

SCHEMA_INVENTION_TYPE: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "invention_type": {
            "type": "string",
            "enum": ["process", "machine", "manufacture", "composition", "design", "none"]
        },
        "rationale": {"type": "string"}
    },
    "required": ["invention_type"]
}

SCHEMA_METHOD_DETAILS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "method_steps": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["method_steps"]
}

SCHEMA_STRUCTURE_DETAILS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "structure_components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "function": {"type": "string"},
                    "relations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["name"]
            }
        },
        "assembly_principles": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["structure_components"]
}

# Simplified schema: CPC Level-1 codes as a JSON array of strings.
SCHEMA_CPC_L1_CODES: Dict[str, Any] = {
    "type": "array",
    "items": {"type": "string"}
}

# Level-2 selection schema: arbitrary object mapping { "G05": "CONTROLLING; REGULATING", ... }
SCHEMA_CPC_L2_DICT: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": {"type": "string"}
}

__all__ = [
    "SCHEMA_INVENTION_TYPE",
    "SCHEMA_METHOD_DETAILS",
    "SCHEMA_STRUCTURE_DETAILS",
    "SCHEMA_CPC_L1_CODES",
    "SCHEMA_CPC_L2_DICT",
]
