# amie/schema/naa_schema.py
# Light JSON Schemas for the NAA node (minimal required fields only)
# Compatible with Python 3.7+ (tested toward 3.13.x)

from typing import Dict, Any


def json_schema(name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrap a bare JSON schema into google-genai's response_format structure.
    Keep it 'strict' to force structured output (no fallbacks elsewhere).
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
            "strict": True,
        },
    }


# 1) Invention type classification
SCHEMA_INVENTION_TYPE: Dict[str, Any] = json_schema(
    "InventionType",
    {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["method", "physical_components"]},
            "reason": {"type": "string"},
        },
        "required": ["type"],
        # Do not set additionalProperties to False (light schema)
    },
)

# 2) Method details (only step name required)
SCHEMA_METHOD_DETAILS: Dict[str, Any] = json_schema(
    "MethodDetails",
    {
        "type": "object",
        "properties": {
            "method_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "string"},
                        "inputs": {"type": "array", "items": {"type": "string"}},
                        "conditions": {"type": "array", "items": {"type": "string"}},
                        "outputs": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["step"],
                },
            }
        },
        "required": ["method_steps"],
    },
)

# 3) Physical components details (only component name required)
SCHEMA_PHYSICAL_DETAILS: Dict[str, Any] = json_schema(
    "PhysicalDetails",
    {
        "type": "object",
        "properties": {
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "materials": {"type": "array", "items": {"type": "string"}},
                        "dimensions": {"type": "array", "items": {"type": "string"}},
                        "interfaces": {"type": "array", "items": {"type": "string"}},
                        "constraints": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name"],
                },
            },
            "assembly": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "relation": {"type": "string"},
                        "details": {"type": "string"},
                    },
                    "required": ["relation", "details"],
                },
            },
        },
        "required": ["components"],
    },
)

# 4) Query synthesis (each item must have q)
SCHEMA_QUERY_SYNTH: Dict[str, Any] = json_schema(
    "QueryBundle",
    {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "minItems": 3,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "q": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["q"],
                },
            }
        },
        "required": ["queries"],
    },
)

# 5) Pairwise comparison / scoring (minimal required keys)
SCHEMA_COMPARE: Dict[str, Any] = json_schema(
    "PairwiseCompare",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "title": {"type": "string"},
            "snippet": {"type": "string"},
            "overlap_features": {"type": "array", "items": {"type": "string"}},
            "difference_features": {"type": "array", "items": {"type": "string"}},
            "llm_similarity_score": {"type": "number"},
            "decision": {"type": "string", "enum": ["likely_similar", "possibly_related", "not_relevant"]},
            "rationale": {"type": "string"},
        },
        "required": ["url", "title", "snippet", "llm_similarity_score", "decision"],
    },
)

# 6) Scalar similarity score (for banding)
SCHEMA_SCORE: Dict[str, Any] = json_schema(
    "SimilarityScore",
    {
        "type": "object",
        "properties": {"score": {"type": "number"}},
        "required": ["score"],
    },
)

# 7) Overall novelty (final integrated list of novel points)
SCHEMA_OVERALL: Dict[str, Any] = json_schema(
    "OverallNovelty",
    {
        "type": "object",
        "properties": {
            "integrated_novelty": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["integrated_novelty"],
    },
)
