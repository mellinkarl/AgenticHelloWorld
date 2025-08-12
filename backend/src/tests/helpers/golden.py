# tests/helpers/golden.py
import json
import pathlib
from typing import Any, Dict, List

def load_golden(path: str) -> Dict[str, Any]:
    """
    Load a 'golden' snapshot JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        The parsed JSON object as a Python dict.
    """
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def assert_match_snapshots(
    recorder_snaps: List[Dict[str, Any]],
    golden: Dict[str, Any]
) -> None:
    """
    Compare recorded state snapshots against a golden reference.

    Args:
        recorder_snaps: List of snapshots produced by StateRecorder.to_dicts().
        golden: The loaded golden snapshot data (expects a "snapshots" key).

    Assertion:
        - Only compares a subset of keys that are relevant to the test:
          {"step", "user_input", "draft", "route", "today", "tool_text",
           "text", "ok", "violations"}.
        - Ignores all other keys, so unrelated changes in the state won't fail the test.

    Raises:
        AssertionError: If the filtered snapshots don't match the golden reference.
    """
    exp = golden["snapshots"]  # Structure inside the golden JSON.
    keys = {
        "step", "user_input", "draft", "route",
        "today", "tool_text", "text", "ok", "violations"
    }

    # Reduce both actual and expected snapshots to only the keys we care about.
    short = [{k: v for k, v in s.items() if k in keys} for s in recorder_snaps]
    short_exp = [{k: v for k, v in s.items() if k in keys} for s in exp]

    assert short == short_exp
