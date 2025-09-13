# amie/agents/utils/cpc_loader.py
# This file loads CPC classification data from local .npy file
# Author: Harry
# 2025-09-14

import os
import numpy as np
from typing import Dict, Any, Tuple


def load_cpc_levels() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load CPC classification (Sections and Classes) from local .npy file.

    Returns:
        dict1 (dict): Original dictionary from .npy
            {
              "level1": {"A": "Human necessities", "B": "...", ...},
              "level2": {"A": {"A01": "Agriculture...", ...}, "B": {...}, ...}
            }
        dict2 (dict): Reformatted strings for easy display
            {
              "level1": "A: Human necessities\nB: Performing operations; ...\n...",
              "level2": {
                  "A": "A01: Agriculture...\nA21: Baking...\n...",
                  "B": "B01: Physical processes...\n..."
              }
            }
    """
    path = os.path.join(os.path.dirname(__file__), "cpc_levels.npy")
    data = np.load(path, allow_pickle=True).item()
    if not isinstance(data, dict):
        raise ValueError("Unexpected CPC data format: expected dict")

    dict1 = data

    # Build dict2
    dict2: Dict[str, Any] = {
        # level1 as single string
        "level1": "\n".join(
            [f"{k}: {v}" for k, v in sorted(dict1["level1"].items())]
        ),
        # level2 as nested strings
        "level2": {}
    }

    for sec, classes in dict1["level2"].items():
        dict2["level2"][sec] = "\n".join([f"{c}: {t}" for c, t in sorted(classes.items())])

    print(dict1)
    return dict1, dict2
