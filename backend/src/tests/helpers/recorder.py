# tests/helpers/recorder.py
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class Snap:
    """
    Represents a snapshot of state captured at a specific step.

    Attributes:
        step: Name or label of the step where the snapshot was taken.
        state: Dictionary representing the state at that step.
    """
    step: str
    state: Dict[str, Any]


class StateRecorder:
    """
    Records and stores snapshots of state across multiple steps.

    Useful in tests for verifying intermediate states, process flow,
    and data changes over time.
    """

    def __init__(self) -> None:
        # Stores all recorded snapshots in order of capture.
        self.snaps: List[Snap] = []

    def push(self, step: str, state: Dict[str, Any]) -> None:
        """
        Record a snapshot of the given state.

        Args:
            step: Label identifying the current step in the process.
            state: A dictionary representing the current state.

        Note:
            - Makes a shallow copy of the state (`dict(state)`) so that
              later modifications to the original state do not affect
              the stored snapshot.
            - Optional: Could be extended to filter out keys before storing.
        """
        self.snaps.append(Snap(step=step, state=dict(state)))

    def to_dicts(self) -> List[Dict[str, Any]]:
        """
        Convert all snapshots to a list of dictionaries.

        Returns:
            A list where each entry is:
                {
                    "step": <step label>,
                    ...<all key-value pairs from the recorded state>...
                }
        """
        return [{"step": s.step, **s.state} for s in self.snaps]
