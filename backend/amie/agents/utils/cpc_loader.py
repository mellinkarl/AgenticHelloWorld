# amie/agents/utils/cpc_loader.py
# This file loads CPC classification data from local .json file
# Author: Harry
# 2025-09-14

import os
import json
from typing import Dict, Any, Tuple

def load_cpc_levels() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns:
      dict1:
        level1 -> original JSON["level1"]
        level2 -> original JSON["level2"]
      dict2:
        level1 -> single newline-joined string:
                  "A: ...\nB: ...\nC: ...\n..."
        level2 -> { section: newline-joined classes string, ... }
    """
    path = os.path.join(os.path.dirname(__file__), "cpc_levels.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # dict1: direct pass-through
    dict1: Dict[str, Any] = {
        "level1": data.get("level1", {}),
        "level2": data.get("level2", {}),
    }

    # dict2: formatted strings
    # level1 -> "A: title\nB: title\n..."
    lvl1_lines = [f"{sec}: {title}" for sec, title in sorted(dict1["level1"].items())]
    dict2_level1 = "\n".join(lvl1_lines) + ("\n" if lvl1_lines else "")

    # level2 -> {"A": "A01: t\nA21: t\n...", "B": "...", ...}
    dict2_level2: Dict[str, str] = {}
    for sec in sorted(dict1["level2"].keys()):
        classes = dict1["level2"][sec]
        cls_lines = [f"{cls}: {title}" for cls, title in sorted(classes.items())]
        dict2_level2[sec] = "\n".join(cls_lines) + ("\n" if cls_lines else "")

    dict2: Dict[str, Any] = {
        "level1": dict2_level1,
        "level2": dict2_level2,
    }

    # print(dict1.get("level1"))
    return dict1, dict2
