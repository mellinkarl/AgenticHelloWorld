# Vertex AI × LangChain — Modular Agents Backend

A minimal, production-oriented backend that separates **reusable atomic agents** from **team-owned composite agents**, running on **Vertex AI (Gemini)**.
Text-only by default; tools are optional and pluggable.

---

## Table of Contents

* [1. Overview](#1-overview)
* [2. Architecture](#2-architecture)
* [3. Directory Structure](#3-directory-structure)
* [4. Config & Credentials (YAML, Overrides, Defaults, Logging)](#4-config--credentials-yaml-overrides-defaults-logging)

  * [4.1 `default.yaml` Content](#41-defaultyaml-content)
  * [4.2 Per-Agent Overrides — Names & Mapping](#42-per-agent-overrides--names--mapping)
  * [4.3 Defaults if Not Overridden](#43-defaults-if-not-overridden)
  * [4.4 ADC vs Local SA key](#44-adc-vs-local-sa-key)
  * [4.5 Logging Config (Location & Method)](#45-logging-config-location--method)
* [5. Prompt (Universal vs Composite-Local vs Dynamic)](#5-prompt-universal-vs-composite-local-vs-dynamic)

  * [5.1 Universal Prompt Selection](#51-universal-prompt-selection)
  * [5.2 Composite-Local Prompt](#52-composite-local-prompt)
  * [5.3 Dynamic Prompt Generation](#53-dynamic-prompt-generation)
  * [5.4 Rule-First + LLM Fallback](#54-rule-first--llm-fallback)
* [6. Atomic Agents (Quick Reference)](#6-atomic-agents-quick-reference)
* [7. Composite Agents](#7-composite-agents)
* [8. Tools & Registry](#8-tools--registry)
* [9. FastAPI (Invoke Any Agent)](#9-fastapi-invoke-any-agent)

  * [9.1 Endpoints](#91-endpoints)
  * [9.2 Request/Response Schemas](#92-requestresponse-schemas)
  * [9.3 Specialized vs Generic Routes](#93-specialized-vs-generic-routes)
* [10. Testing (with Goldens)](#10-testing-with-goldens)
* [11. Local Runners (Temporary)](#11-local-runners-temporary)
* [12. Development Workflow](#12-development-workflow)
* [13. Roadmap / TODO](#13-roadmap--todo)
* [Appendix A — Agents Detail](#appendix-a--agents-detail)

---

## 1. Overview

* **Atomic Agent**: Reads `state: Dict[str, Any]` and returns a small **delta dict** to be merged.
* **Composite Agent**: Orchestrates multiple atomic agents, exposing the same `.invoke()` interface.
* **Prompts**: Three types — **Universal Registry**, **Composite-Local**, **Dynamic Generation**.
* **Tools**: Python callables, registered once, invoked via a lightweight agent wrapper.
* Config automatically supports **ADC and Local SA key**; logging is **structured JSON**.

---

## 2. Architecture

1. Request arrives (HTTP / Local Runner) with `state`.
2. **Agent** executes: reads only the required keys, returns delta.
3. Controller/Composite merges delta into `state`, proceeds to next step.
4. Output normalized (`{"text": "..."}` or `{"json": {...}}`).

Supports:

* **Sync**: `invoke(state) -> Dict[str, Any]`
* **Async placeholder**: `ainvoke(state) -> Dict[str, Any]` (upgradeable to async/streaming)

---

## 3. Directory Structure

```bash
src/
├── agents/                          # Atomic Agents (reusable)
│   ├── diff_enforcer_agent.py
│   ├── length_keyword_guard_agent.py
│   ├── llm_router_agent.py
│   ├── llm_runner_agent.py
│   ├── python_tool_agent.py
│   ├── refiner_agent.py
│   ├── rule_router_agent.py
│   ├── schema_enforcer_agent.py
│   └── template_filler_agent.py
│
├── app/                              # FastAPI app & routes
│   ├── main.py
│   └── routes/
│
├── composite_agents/                 # Team-owned composite agents
│   └── test_linear/
│
├── config/                           # Config & logging
│   ├── config.py
│   ├── default.yaml
│   └── logging_config.py
│
├── core/                             # Protocols & instrumentation
│   ├── agent_protocol.py
│   ├── context.py
│   ├── instrumentation.py
│   └── logging_utils.py
│
├── llm/                              # LLM wrapper
│   └── vertex.py
│
├── prompts/                          # Universal prompts & registry
│   ├── __init__.py
│   ├── base_prompt.py
│   ├── llm_router_prompt.py
│   └── refiner_prompt.py
│
├── runner/                           # Local runners
│   └── run_composite_test.py
│
├── tools/                            # Tool functions & registry
│   ├── registry.py
│   └── date_tool.py
│
├── tests/                            # Tests & helpers
│   ├── helpers/
│   └── ...
└── probe_vertex.py
```

---

## 4. Config & Credentials (YAML, Overrides, Defaults, Logging)

### 4.1 `default.yaml` Content (Extended Version)

```yaml
# GCP / Auth
project: your-gcp-project
location: us-central1
credentials_name: your-service-account.json

# Global LLM defaults
model_name: gemini-2.0-flash
temperature: 0.2
top_p: 0.95
top_k: 40
candidate_count: 1
max_output_tokens: 1024
response_mime_type: text/plain
system_instruction: ""
stop_sequences: []
timeout_s: 60

# Per-Agent overrides
agents:
  runner:
    temperature: 0.1
    system_instruction: "Be brief and literal."
  refiner:
    max_output_tokens: 1024
  decider:
    temperature: 0.0
    system_instruction: "You only decide route labels."

# Retry policy
retry:
  max_attempts: 3
  initial_backoff_s: 0.5
  max_backoff_s: 8.0
  multiplier: 2.0

# Logging
logging:
  level: INFO
  format: json
  include_request_id: true
  file: logs/app.log
  rotate_mb: 10
  rotate_backups: 5
```

### 4.2 Per-Agent Overrides — Names & Mapping

| YAML Key | Agent Class    | Example Call                             |
| -------- | -------------- | ---------------------------------------- |
| runner   | LLMRunnerAgent | `get_vertex_chat_model(agent="runner")`  |
| refiner  | RefinerAgent   | `get_vertex_chat_model(agent="refiner")` |
| decider  | LLMRouterAgent | `get_vertex_chat_model(agent="decider")` |

### 4.3 Defaults if Not Overridden

Falls back to global `model_name`, `temperature`, etc.

### 4.4 ADC vs Local SA key

* `USE_ADC=true` → Application Default Credentials
* Otherwise use `GOOGLE_APPLICATION_CREDENTIALS` or `src/.keys/{credentials_name}`

### 4.5 Logging Config

See `src/config/logging_config.py`.
Each agent logs `invoke.start` and `invoke.end` (with preview, result, elapsed ms).

---

## 5. Prompt (Universal vs Composite-Local vs Dynamic)

### 5.1 Universal Prompt Selection

Located in `src/prompts/`, registered in `PROMPTS`.
HTTP example:

```bash
curl -X POST localhost:8000/agents/LLMRunnerAgent/invoke \
  -H 'content-type: application/json' \
  -d '{"state":{"user_input":"Say OK"},"args":{"prompt_name":"runner/personal"}}'
```

### 5.2 Composite-Local Prompt

Placed in `src/composite_agents/<name>/prompts/`, used only by that composite:

```python
from src.agents.llm_router_agent import LLMRouterAgent
from .prompts.route_v1 import ROUTE_PROMPT

state.update(LLMRouterAgent(prompt=ROUTE_PROMPT).invoke(state))
```

### 5.3 Dynamic Prompt Generation

Constructed based on `state` or config:

```python
from langchain_core.prompts import ChatPromptTemplate
from src.config.config import Config
from src.agents.llm_runner_agent import LLMRunnerAgent

cfg = Config.load()
sys_msg = f"You are a {state.get('domain','generic')} assistant."
prompt = ChatPromptTemplate.from_messages([("system", sys_msg), ("user", "{user_input}")])

state.update(LLMRunnerAgent(prompt=prompt, llm_kwargs=cfg.llm_kwargs(agent="runner", temperature=0.1)).invoke(state))
```

### 5.4 Rule-First + LLM Fallback

Run `RuleRouterAgent` first, then LLM if undecided:

```python
state.update(RuleRouterAgent(rules={...}, default_route="llm_decide").invoke(state))
if state.get("route") == "llm_decide":
    state.update(LLMRouterAgent(prompt=ROUTE_PROMPT).invoke(state))
```

---

## 6. Atomic Agents (Quick Reference)

| Agent                   | Purpose                     | Reads                 | Writes             |
| ----------------------- | --------------------------- | --------------------- | ------------------ |
| LLMRunnerAgent          | Prompt → LLM → draft        | `user_input`          | `draft`            |
| RuleRouterAgent         | Rule-based routing          | `draft`               | `route`, `reasons` |
| LLMRouterAgent          | LLM decision routing        | `user_input`, `draft` | `route`, `raw`     |
| RefinerAgent            | Rewrite (preserve intent)   | `draft`               | `text`             |
| SchemaEnforcerAgent     | Normalize to text/JSON      | `text`/`draft`        | `text`/`json`      |
| LengthKeywordGuardAgent | Length/keyword checks       | `text`                | `ok`, `violations` |
| DiffEnforcerAgent       | Ensure `text` ≠ `draft`     | `draft`, `text`       | `text`             |
| PythonToolAgent         | Call registered tool        | kwargs                | `<output_key>`     |
| TemplateFillerAgent     | Render `.format()` template | template keys         | `<output_key>`     |

---

## 7. Composite Agents

Composite agents chain atomic agents, may include local prompts and conditional logic. Maintained independently by teams.

---

## 8. Tools & Registry

Place functions in `src/tools/` and register in `registry.py`.
Call via `PythonToolAgent` and write to target key.

---

## 9. FastAPI (Invoke Any Agent)

Start:

```bash
uvicorn src.app.main:app --reload --port 8000
```

### 9.1 Endpoints

* `GET /agents` → list agents
* `POST /agents/{agent_name}/invoke` → generic call
* Specialized: `/agents/python-tool/invoke`, `/agents/template-filler/invoke`

### 9.2 Request/Response Schemas

* Request: `state`, `args` (optional), `async_mode`
* Response: `agent`, `ms`, `state_in`, `state_out`

### 9.3 Specialized vs Generic Routes

Specialized: clearer params; Generic: handles all remaining agents.

---

## 10. Testing (with Goldens)

Tests in `src/tests/`, run with `pytest -q`.
`--write-goldens` updates baseline files.

---

## 11. Local Runners (Temporary)

Quick test under `src/runner/`; `probe_vertex.py` checks environment and config.

---

## 12. Development Workflow

1. Add/modify atomic agent in `src/agents/`
2. Place prompts in universal or composite-local
3. Create/extend composite in `src/composite_agents/`
4. Register tools
5. Test via HTTP or local runner
6. Add tests and update goldens

---

## 13. Roadmap / TODO

* Support streaming (`astream_events`) + SSE/WebSocket
* Expand universal prompts; add health checks
* More composite examples
* Latency/Token monitoring & optimization
* Update `probe_vertex.py`

---

## Appendix A — Agents Detail

**LLMRunnerAgent**
Reads: `user_input` → Writes: `draft`, supports `args.prompt_name` for prompt injection

**RuleRouterAgent**
Rule-based routing → Writes: `route`, `reasons`

**LLMRouterAgent**
LLM-based routing → Writes: `route`, `raw`

**RefinerAgent**
Light rewrite → Writes: `text`

**SchemaEnforcerAgent**
Normalize to `{"text": ...}` or `{"json": ...}`

**LengthKeywordGuardAgent**
Checks length & keywords → Writes: `ok`, `violations`

**DiffEnforcerAgent**
Ensures `text` differs from `draft`

**PythonToolAgent**
Calls registered tool → Writes `<output_key>`

**TemplateFillerAgent**
Renders `.format()` template → Writes `<output_key>`

---