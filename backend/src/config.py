# config.py
# Load config from YAML (default.yaml) or env vars (ADC).
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import vertexai
import yaml
from google.oauth2.service_account import Credentials

# Global switches
USE_ADC = os.getenv("USE_ADC", "false").lower() == "true"  # default local: False
BASE_DIR = Path(__file__).resolve().parent                  # <repo>/src
DEFAULT_YAML = BASE_DIR / "config" / "default.yaml"        # src/config/default.yaml
DEFAULT_KEYS_DIR = BASE_DIR / ".keys"                      # src/.keys/


def _load_config(path: Path) -> Dict[str, Any]:
    """
    Load config from YAML (preferred) or JSON (if path endswith .json).
    YAML supports comments (# ...). Returns {} if file missing/empty.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        if path.suffix.lower() == ".json":
            return json.loads(text)
        # default: YAML
        data = yaml.safe_load(text)
        return data or {}
    except Exception as e:
        raise ValueError(f"Failed to parse config file: {path} ({e})") from e


@dataclass
class LLMDefaults:
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.2
    max_output_tokens: int = 512
    response_mime_type: str = "text/plain"


@dataclass
class Config:
    # Cloud project/region (may come from env or YAML)
    project: Optional[str] = None
    location: Optional[str] = None

    # Credentials strategy
    credentials_name: Optional[str] = None  # e.g., "a.json" under src/.keys/

    # Global LLM defaults (agents may override)
    llm: LLMDefaults = field(default_factory=LLMDefaults)

    # Agent-level overrides, e.g. {"runner": {"model_name": "..."}}
    agents: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Debug source info
    _source: str = "defaults"

    @classmethod
    def load(cls, yaml_path: Path = DEFAULT_YAML) -> "Config":
        # 1) YAML (or JSON) config file
        y = _load_config(yaml_path)
        cfg = cls(
            project=y.get("project"),
            location=y.get("location"),
            credentials_name=y.get("credentials_name"),
            llm=LLMDefaults(
                model_name=y.get("model_name", LLMDefaults.model_name),
                temperature=y.get("temperature", LLMDefaults.temperature),
                max_output_tokens=y.get("max_output_tokens", LLMDefaults.max_output_tokens),
                response_mime_type=y.get("response_mime_type", LLMDefaults.response_mime_type),
            ),
            agents=y.get("agents", {}) if isinstance(y.get("agents", {}), dict) else {},
            _source=f"file:{yaml_path}" if y else "defaults",
        )

        # 2) Env overrides (highest precedence for project/location)
        cfg.project = os.getenv("GOOGLE_CLOUD_PROJECT", cfg.project)
        cfg.location = os.getenv("GOOGLE_CLOUD_REGION", cfg.location)

        # 3) Minimal sanity
        if not cfg.project or not cfg.location:
            raise ValueError(
                "Project/location not set. Provide via src/config/default.yaml or env "
                "[GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_REGION]."
            )
        return cfg

    # ----- Credentials resolution -----
    def resolve_credentials_path(self) -> Optional[Path]:
        """
        Returns a local service-account json path when not using ADC.
        Priority:
          1) GOOGLE_APPLICATION_CREDENTIALS (absolute path)
          2) src/.keys/{credentials_name}
          3) None (if USE_ADC=True) or raise if missing
        """
        if USE_ADC:
            return None
        gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if gac:
            p = Path(gac).expanduser().resolve()
            if not p.exists():
                raise FileNotFoundError(f"GOOGLE_APPLICATION_CREDENTIALS not found: {p}")
            return p
        if self.credentials_name:
            p = (DEFAULT_KEYS_DIR / self.credentials_name).resolve()
            if not p.exists():
                raise FileNotFoundError(f"Local credentials not found at: {p}")
            return p
        raise ValueError(
            "No credentials provided. Set USE_ADC=true or set GOOGLE_APPLICATION_CREDENTIALS "
            "or provide 'credentials_name' in default.yaml."
        )

    def apply_google_env(self) -> None:
        """Export env vars for libs relying on ADC env (even when using explicit creds locally)."""
        if USE_ADC:
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        else:
            cred_path = self.resolve_credentials_path()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.project or ""
        os.environ["GOOGLE_CLOUD_REGION"] = self.location or ""

    def load_credentials(self) -> Optional[Credentials]:
        """Returns Credentials object for explicit auth (None under ADC)."""
        if USE_ADC:
            return None
        cred_path = self.resolve_credentials_path()
        return Credentials.from_service_account_file(
            str(cred_path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    # ----- LLM helpers -----
    def llm_kwargs(self, agent: Optional[str] = None, **overrides) -> Dict[str, Any]:
        """
        Build kwargs for ChatVertexAI (project/location + model/params),
        merging defaults <- agent override <- runtime overrides.
        """
        base = {
            "project": self.project,
            "location": self.location,
            "model": self.llm.model_name,
            "temperature": self.llm.temperature,
            "max_output_tokens": int(self.llm.max_output_tokens),
            "response_mime_type": self.llm.response_mime_type,
        }
        # agent-level overrides from config
        if agent and agent in self.agents:
            base.update(self.agents[agent])
        # call-site overrides
        base.update(overrides)
        return base

    def init_vertex(self) -> None:
        """Initialize Vertex endpoint once."""
        vertexai.init(project=self.project, location=self.location)

    # Debug dump
    def debug_print(self) -> None:
        d = asdict(self)
        d.pop("_source", None)
        print(json.dumps(d, ensure_ascii=False, indent=2))
