
# 🌈 Universal Agents — Full Reference

This folder contains **reusable, atomic agents**.  
Each agent is a single-step function that **reads** from a shared `state` dict and **returns** a small delta dict to merge back into `state`.

- **Sync:** `invoke(state: Mapping[str, Any]) -> Dict[str, Any>`
- **Async:** `ainvoke(state: Mapping[str, Any]) -> Dict[str, Any>` (real async if implemented)
- **State format:** plain Python `dict` (JSON-serializable). Over HTTP (FastAPI), you send/receive JSON.

Agents only **read the keys they need** and avoid side effects unless explicitly designed (e.g., <span style="color:#009688;font-weight:bold">PythonToolAgent</span>).

---

## 🔗 Quick Links

- [Summary Table](#-summary-table)
- [Where Configs & Prompts Live](#-where-configs--prompts-live)
- [Agent Details](#-agent-details)
  - [LLMRunnerAgent](#llmrunneragent)
  - [RuleRouterAgent](#rulerouteragent)
  - [LLMRouterAgent](#llmrouteragent)
  - [RefinerAgent](#refineragent)
  - [SchemaEnforcerAgent](#schemaenforceragent)
  - [LengthKeywordGuardAgent](#lengthkeywordguardagent)
  - [DiffEnforcerAgent](#diffenforceragent)
  - [PythonToolAgent](#pythontoolagent)
  - [TemplateFillerAgent](#templatefilleragent)
- [Example Pipeline](#-example-pipeline)
- [Personal Prompt (How-To)](#-adding-a-personal-prompt)
- [Custom Route Rules (Rule-based & LLM-based)](#-adding-a-custom-route-rule)
- [Logging & Observability](#-logging--observability)
- [FAQ](#-faq)
- [See Also](#-see-also)

---

## 📋 Summary Table

| Agent | Purpose | Reads | Writes |
| ----- | ------- | ----- | ------ |
| [<span style="color:#009688;font-weight:bold">LLMRunnerAgent</span>](#llmrunneragent) | Prompt → LLM → string draft | <span style="color:#FF9800">user_input</span> | <span style="color:#FF9800">draft</span> |
| [<span style="color:#009688;font-weight:bold">RuleRouterAgent</span>](#rulerouteragent) | Rule-based routing (no tokens) | <span style="color:#FF9800">draft</span> | <span style="color:#FF9800">route</span>, <span style="color:#FF9800">reasons</span> |
| [<span style="color:#009688;font-weight:bold">LLMRouterAgent</span>](#llmrouteragent) | LLM-based routing decision | <span style="color:#FF9800">user_input</span>, <span style="color:#FF9800">draft</span> | <span style="color:#FF9800">route</span>, <span style="color:#FF9800">raw</span> |
| [<span style="color:#009688;font-weight:bold">RefinerAgent</span>](#refineragent) | Light rewrite (keep intent) | <span style="color:#FF9800">draft</span> | <span style="color:#FF9800">text</span> |
| [<span style="color:#009688;font-weight:bold">SchemaEnforcerAgent</span>](#schemaenforceragent) | Normalize to text/JSON | <span style="color:#FF9800">text</span> / <span style="color:#FF9800">draft</span> | <span style="color:#FF9800">text</span> / <span style="color:#FF9800">json</span> |
| [<span style="color:#009688;font-weight:bold">LengthKeywordGuardAgent</span>](#lengthkeywordguardagent) | Objective checks (len/keywords/regex) | <span style="color:#FF9800">text</span> | <span style="color:#FF9800">ok</span>, <span style="color:#FF9800">violations</span> |
| [<span style="color:#009688;font-weight:bold">DiffEnforcerAgent</span>](#diffenforceragent) | Ensure `text` differs from `draft` | <span style="color:#FF9800">draft</span>, <span style="color:#FF9800">text</span> | <span style="color:#FF9800">text</span> |
| [<span style="color:#009688;font-weight:bold">PythonToolAgent</span>](#pythontoolagent) | Run a registered Python tool | tool kwargs | `<output_key>` |
| [<span style="color:#009688;font-weight:bold">TemplateFillerAgent</span>](#templatefilleragent) | Render `.format()` template | template keys | `<output_key>` |

> Keys not listed are **ignored** by that agent.

---

## 🧭 Where Configs & Prompts Live

- **Vertex LLM defaults:** `src/config/default.yaml` (e.g., `project`, `location`, `model_name`, `temperature`, etc.)
  - Per-agent override:
    ```yaml
    agents:
      runner:
        temperature: 0.1
      refiner:
        max_output_tokens: 1024
    ```
- **Prompts:** `src/prompts/`
- **Tools:** register in `src/tools/registry.py`
- **Logging:** structured JSON logger in `src/config/logging_config.py`

---

## 🧩 Agent Details

### LLMRunnerAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Standardize one LLM call (prompt → model → parse → string).  
**Reads:** <span style="color:#FF9800">user_input</span>  
**Writes:** <span style="color:#FF9800">draft</span>  

- Uses `BASE_PROMPT` → Vertex `ChatVertexAI` → `StrOutputParser`.
- Real async via `chain.ainvoke` when using `ainvoke`.
- Customize by overriding `agents.runner` in YAML, or clone and swap the prompt.

---

### RuleRouterAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Fast deterministic routing (no tokens).  
**Reads:** <span style="color:#FF9800">draft</span>  
**Writes:** <span style="color:#FF9800">route</span> (`PASS`/`REFINE`), <span style="color:#FF9800">reasons</span>  

**Config params (constructor):**  
<span style="color:#FF9800">min_len</span>, <span style="color:#FF9800">max_len</span>,  
<span style="color:#FF9800">must_include</span>, <span style="color:#FF9800">forbid</span>,  
<span style="color:#FF9800">require_json</span>, <span style="color:#FF9800">regex</span>,  
<span style="color:#FF9800">pass_route</span>, <span style="color:#FF9800">fail_route</span>

- Evaluates in order; first failing rule decides the route.
- `reasons` lists the failure cause (e.g., `["min_len<10"]`).

---

### LLMRouterAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** LLM-based decision when rules aren’t enough.  
**Reads:** <span style="color:#FF9800">user_input</span>, <span style="color:#FF9800">draft</span>  
**Writes:** <span style="color:#FF9800">route</span> (`PASS`/`REFINE`/`REFINE_DATE`), <span style="color:#FF9800">raw</span>  

- Uses `LLM_ROUTER_PROMPT` and normalizes raw output to the allowed token set.
- Clone to plug custom decisions/tokens via your prompt.

---

### RefinerAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Light rewrite; keep intent, improve clarity/format/completeness.  
**Reads:** <span style="color:#FF9800">draft</span>  
**Writes:** <span style="color:#FF9800">text</span>  

- Pass <span style="color:#FF9800">requirements</span> to adjust strictness and style.
- Can be cloned to use a different prompt template.

---

### SchemaEnforcerAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Normalize to **text** or **JSON** (optional Pydantic validation).  
**Reads:** <span style="color:#FF9800">prefer_key</span> (default `text`) → else `text` → else `draft`  
**Writes:** <span style="color:#FF9800">text</span> **or** <span style="color:#FF9800">json</span>  

- Mode `"text"` → choose best available text-like field and return `{"text": "..."}`.  
- Mode `"json"` → `json.loads` + optional Pydantic validation; fallback `{"text": raw}`.

---

### LengthKeywordGuardAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Objective checks (length / required keywords / forbidden keywords / regex).  
**Reads:** <span style="color:#FF9800">text</span> (or custom `source_key`)  
**Writes:** <span style="color:#FF9800">ok</span>, <span style="color:#FF9800">violations</span>  

- Collects **all** violations (no short-circuit).

---

### DiffEnforcerAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Ensure final <span style="color:#FF9800">text</span> differs from <span style="color:#FF9800">draft</span>.  
**Reads:** <span style="color:#FF9800">draft</span>, <span style="color:#FF9800">text</span>  
**Writes:** <span style="color:#FF9800">text</span>  

- If equal:
  - If <span style="color:#FF9800">use_suffix_key</span> present and <span style="color:#FF9800">replace_with_key=True</span> → **replace** with that value
  - Else **append** suffix (default `" (modified)"`)

---

### PythonToolAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Run a registered Python callable and stash result into state.  
**Reads:** keys mapped via <span style="color:#FF9800">kwargs_from_state</span>  
**Writes:** `<output_key>`  

- Register tools in `src/tools/registry.py`.
- Async-aware (awaits async tools; runs sync tools in a thread via the registry).

---

### TemplateFillerAgent
**Color:** <span style="color:#009688;font-weight:bold">teal</span>  
**Purpose:** Render a Python `.format()` template from `state` (non-strict).  
**Reads:** template placeholders  
**Writes:** `<output_key>` (default <span style="color:#FF9800">text</span>)  

- Missing keys do **not** raise; returns the template unchanged.

---

## 🧪 Example Pipeline

```python
state = {"user_input": "Say exactly: OK."}

# 1) Generate draft
state.update(LLMRunnerAgent().invoke(state))  # -> {"draft": "OK."}

# 2) Route by rules (fast)
state.update(RuleRouterAgent(min_len=1).invoke(state))  # -> {"route": "PASS", "reasons": []}

# 3) Optional refine
if state["route"] != "PASS":
    state.update(RefinerAgent().invoke(state))          # -> {"text": "..."}
else:
    state["text"] = state["draft"]

# 4) Guard checks
state.update(LengthKeywordGuardAgent(must_include=["OK"]).invoke(state))

# 5) Normalize final
state.update(SchemaEnforcerAgent(mode="text").invoke(state))

print(state["text"])  # "OK."
````

---

## ✍️ Adding a Personal Prompt

**Clone & swap** (keep the same interface, swap the prompt):

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .llm_runner_agent import LLMRunnerAgent

MY_PROMPT = ChatPromptTemplate.from_messages([
  ("system", "You are an expert in X. Follow strict format Y."),
  ("user", "{user_input}")
])

class MyRunnerAgent(LLMRunnerAgent):
    def __init__(self, llm=None):
        super().__init__(llm)
        self.chain = MY_PROMPT | self.llm | StrOutputParser()
```

**Composite-only alternative:** keep universal agents generic; in your composite, implement a step that calls a custom chain (your prompt + model + parser) and writes to `state`.

---

## 🛤️ Adding a Custom Route Rule

You can do **rule-based** (fast, local) or **LLM-based** (flexible).

### A) Rule-based custom router (s1/s2 manuscripts)

```python
# src/agents/manuscript_router_agent.py
from __future__ import annotations
from typing import Mapping, Dict, Any, List
from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end

log = get_logger(__name__)

class ManuscriptNoveltyRouterAgent:
    """
    Decide novelty based on two manuscripts: s1, s2.
    Emits routes: NOVEL, NOT_NOVEL, HUMAN_CHECK, and sets statusxxx accordingly.
    """
    def __init__(self, *, overlap_threshold: float = 0.6):
        self.overlap_threshold = overlap_threshold

    @staticmethod
    def _tokens(s: str) -> List[str]:
        return [w.lower() for w in s.split() if w.isalnum()]

    def invoke(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        t0 = log_invoke_start(log, "ManuscriptNoveltyRouterAgent", state)
        s1 = str(state.get("s1", "")); s2 = str(state.get("s2", ""))

        t1 = set(self._tokens(s1)); t2 = set(self._tokens(s2))
        inter = len(t1 & t2); union = len(t1 | t2) or 1
        jaccard = inter / union

        if jaccard < 0.3:
            route, statusxxx = "NOVEL", "novel_invention"
        elif jaccard > self.overlap_threshold:
            route, statusxxx = "NOT_NOVEL", "known_or_obvious"
        else:
            route, statusxxx = "HUMAN_CHECK", "borderline_50_50"

        out = {"route": route, "statusxxx": statusxxx, "similarity": jaccard}
        log_invoke_end(log, "ManuscriptNoveltyRouterAgent", t0, out)
        return out
```

**Use in a composite:**

```python
state = {"s1": "...", "s2": "..."}
state.update(ManuscriptNoveltyRouterAgent(overlap_threshold=0.65).invoke(state))
if state["route"] == "NOVEL":
    ...
elif state["route"] == "NOT_NOVEL":
    ...
else:  # HUMAN_CHECK
    ...
```

### B) LLM-based custom router (s1/s2 manuscripts)

```python
# src/agents/manuscript_llm_router_agent.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ..llm.vertex import get_vertex_chat_model
from ..config import get_logger
from ..core.instrumentation import log_invoke_start, log_invoke_end

log = get_logger(__name__)

PROMPT = ChatPromptTemplate.from_messages([
  ("system",
   "You are a strict novelty judge for patent-style manuscripts.\n"
   "Return ONLY one token: NOVEL | NOT_NOVEL | HUMAN_CHECK.\n"
   "Criteria: If obviously novel -> NOVEL; obviously non-novel/obvious -> NOT_NOVEL; borderline 50/50 -> HUMAN_CHECK.\n"
   "No explanation."),
  ("user", "Manuscript A:\n{s1}\n\nManuscript B:\n{s2}\n\nDecision:")
])

class ManuscriptLLMRouterAgent:
    def __init__(self, llm=None):
        self.llm = llm or get_vertex_chat_model(agent="decider")
        self.chain = PROMPT | self.llm | StrOutputParser()

    def invoke(self, state):
        t0 = log_invoke_start(log, "ManuscriptLLMRouterAgent", state)
        s1 = str(state.get("s1", "")); s2 = str(state.get("s2", ""))
        raw = self.chain.invoke({"s1": s1, "s2": s2}).strip().upper()
        route = raw if raw in {"NOVEL", "NOT_NOVEL", "HUMAN_CHECK"} else "HUMAN_CHECK"
        statusxxx = {
          "NOVEL": "novel_invention",
          "NOT_NOVEL": "known_or_obvious",
          "HUMAN_CHECK": "borderline_50_50"
        }[route]
        out = {"route": route, "statusxxx": statusxxx, "raw": raw}
        log_invoke_end(log, "ManuscriptLLMRouterAgent", t0, out)
        return out
```

**FastAPI example:**

```bash
curl -X POST localhost:8000/agents/ManuscriptLLMRouterAgent/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"s1":"...","s2":"..."}}'
```

---

## 📜 Logging & Observability

Every agent emits **structured JSON logs**:

* **start:** input keys, short previews (`user_input`, `draft`, `text`)
* **end:** output keys, short previews, <span style="color:#FF9800">ms</span> duration, special flags (e.g., `route`, `ok`, `violations`)
* **request\_id:** attached when present (FastAPI middleware)

This makes pipelines auditable and easy to debug.

---

## ❓ FAQ

**Q: Is `state` a JSON or a dict?**
A: Internally, a Python `dict`. Over HTTP it’s JSON. Keep values JSON-serializable.

**Q: Where do agents fetch data?**
A: They don’t. Agents read from keys already in `state`. Provide external data via:

* A previous step/agent (e.g., <span style="color:#009688;font-weight:bold">PythonToolAgent</span> writes `today`)
* Your composite/controller (you set keys)

**Q: How do I add a personal prompt?**
A: Clone the agent and swap the prompt (see [Adding a Personal Prompt](#-adding-a-personal-prompt)). Or build a custom chain inside a composite step.

**Q: Can I stream tokens?**
A: Yes—several agents have `ainvoke`. You can also implement streaming (`astream_events`) and expose via SSE/WebSocket at the API layer.

**Q: Logging too terse/verbose?**
A: Adjust levels/format in `config/default.yaml` and `logging_config.py`.

---

## 🔭 See Also

* `src/composite_agents/` — chaining examples
* `src/tools/registry.py` — register sync/async tools
* `src/prompts/` — shared prompt templates
* `src/app/` — FastAPI endpoints to run and test agents

