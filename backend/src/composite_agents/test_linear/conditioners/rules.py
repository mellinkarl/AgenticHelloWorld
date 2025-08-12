from __future__ import annotations

# Local rule presets for RuleRouterAgent and Guard
RULES = {
    "router": {
        "min_len": 1,
        "max_len": 2000,
        "must_include": [],
        "forbid": [],
        "require_json": False,
        "regex": None,
    },
    "guard": {
        "min_len": 1,
        "max_len": 2000,
        "must_include": ["OK"],  # demo: require OK in final text
        "forbid": [],
        "regex": None,
    }
}
