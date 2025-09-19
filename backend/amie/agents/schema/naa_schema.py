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

# Used for machine-like physical structures
SCHEMA_MACHINE_DETAILS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "function": {"type": "string"},
                    "key_specs": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "subsystems": {"type": "array", "items": {"type": "string"}},
        "connections": {"type": "array", "items": {"type": "string"}},
        "operating_principles": {"type": "array", "items": {"type": "string"}},
        "materials": {"type": "array", "items": {"type": "string"}},
        "sensors_actuators": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["components"]
}

# Article of manufacture details
SCHEMA_MANUFACTURE_DETAILS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "article_components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "function": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "materials": {"type": "array", "items": {"type": "string"}},
        "dimensions": {"type": "array", "items": {"type": "string"}},
        "manufacturing_steps": {"type": "array", "items": {"type": "string"}},
        "assembly": {"type": "array", "items": {"type": "string"}},
        "tolerances": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["article_components"]
}

# Composition of matter details
SCHEMA_COMPOSITION_DETAILS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "constituents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "amount": {"type": "string"}
                },
                "required": ["name"]
            }
        },
        "synthesis_steps": {"type": "array", "items": {"type": "string"}},
        "properties": {"type": "array", "items": {"type": "string"}},
        "use_cases": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["constituents"]
}

# Design patent details
SCHEMA_DESIGN_DETAILS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "ornamental_features": {"type": "array", "items": {"type": "string"}},
        "views": {"type": "array", "items": {"type": "string"}},
        "non_functional_statement": {"type": "string"},
        "claim_scope_note": {"type": "string"}
    },
    "required": ["ornamental_features"]
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
    "SCHEMA_MACHINE_DETAILS",
    "SCHEMA_MANUFACTURE_DETAILS",
    "SCHEMA_COMPOSITION_DETAILS",
    "SCHEMA_DESIGN_DETAILS",
    "SCHEMA_CPC_L1_CODES",
    "SCHEMA_CPC_L2_DICT",
]
