# amie/agents/utils/cpc_extracter.py
# This file extracts CPC classification data from Title List ZIP into JSON/NPY
# Author: Harry
# 2025-09-14

"""
Parse CPC Title List ZIP (per-section TXT files, TAB-separated) and save JSON:
{
  "level1": { "A": "...", "B": "...", ... },
  "level2": { "A": {"A01":"...", ...}, "B": {...}, ... }
}

Rules (per your spec):
- Each line, first field:
    len==1  -> level1 (Section)
    len==3  -> level2 (Class)
- Each line, the SECOND field is the description (fallback to third if empty).
- Ignore all other lines (subclass, groups, etc).
- Iterate every cpc-section-*.txt in the zip.

Usage:
   python amie/agents/utils/cpc_extract.py --zip amie/agents/utils/CPCTitleList202508.zip --out amie/agents/utils/cpc_levels.npy
                                                                                                                    or .json
"""

import argparse
import json
import os
import zipfile
from typing import Dict

def parse_zip(zip_path: str) -> Dict[str, dict]:
    level1: Dict[str, str] = {}
    level2: Dict[str, Dict[str, str]] = {}

    with zipfile.ZipFile(zip_path, 'r') as z:
        # only the per-section text files
        section_files = [
            n for n in z.namelist()
            if n.lower().startswith("cpc-section-") and n.lower().endswith(".txt")
        ]
        if not section_files:
            raise RuntimeError("No cpc-section-*.txt files found in the ZIP.")

        for name in sorted(section_files):
            with z.open(name) as f:
                data = f.read().decode("utf-8", errors="replace")

            for line in data.splitlines():
                if not line.strip():
                    continue

                parts = line.split("\t")
                if len(parts) < 2:
                    continue

                code = parts[0].strip()
                # per your spec, the 2nd field is the description
                desc = parts[1].strip() if len(parts) >= 2 else ""
                if not desc and len(parts) >= 3:
                    # fallback if file has double tabs like "E\t\tFIXED ..."
                    desc = parts[2].strip()

                if not code or not desc:
                    continue

                # level1: first token length == 1 (e.g., "E")
                if len(code) == 1:
                    level1[code] = desc
                    continue

                # level2: first token length == 3 (e.g., "E01")
                if len(code) == 3 and code[0].isalpha() and code[1:].isdigit():
                    sec = code[0]
                    level2.setdefault(sec, {})
                    level2[sec][code] = desc
                    continue

                # ignore everything else (subclass/groups like E01B, E01B1/00, etc.)
                # pass

    return {"level1": level1, "level2": level2}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="Path to CPCTitleList*.zip")
    ap.add_argument("--out", required=True, help="Output JSON path (e.g., cpc_levels.json)")
    ap.add_argument("--indent", type=int, default=2, help="JSON indent")
    args = ap.parse_args()

    data = parse_zip(args.zip)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=args.indent)

    sections = len(data["level1"])
    classes = sum(len(v) for v in data["level2"].values())
    print(f"[OK] Wrote JSON: {args.out}")
    print(f"  Sections: {sections}, Classes: {classes}")

if __name__ == "__main__":
    main()