# src/config/config.py
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional
from google.oauth2.service_account import Credentials as _SACredentials
import vertexai

import yaml

DEFAULT_YAML = Path(__file__).with_name("default.yaml")

# --------- helpers ---------
def _load_yaml(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")

def _coalesce_env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for n in names:
        if os.getenv(n):
            return os.getenv(n)
    return default

# --------- dataclasses for config ---------
@dataclass
class LLMDefaults:
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.2
    top_p: float = 0.95
    top_k: int = 40
    candidate_count: int = 1
    max_output_tokens: int = 1024
    response_mime_type: str = "text/plain"
    system_instruction: Optional[str] = None
    stop_sequences: list[str] = field(default_factory=list)
    timeout_s: int = 60

@dataclass
class LoggingDefaults:
    level: str = "INFO"
    format: str = "json"  # json | pretty
    include_request_id: bool = True
    file: Optional[str] = None
    rotate_mb: int = 10
    rotate_backups: int = 5

@dataclass
class Config:
    # Source info (optional, handy for debugging)
    _source: str = "defaults"

    # Cloud & Auth
    project: Optional[str] = None
    location: Optional[str] = None
    api_endpoint: Optional[str] = None
    credentials_name: Optional[str] = None
    use_adc: bool = False

    # Global LLM defaults
    llm: LLMDefaults = field(default_factory=LLMDefaults)

    # Agent-level overrides for LLM-backed agents
    agents: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Logging
    logging: LoggingDefaults = field(default_factory=LoggingDefaults)

    # App-level retry policy (not SDK-enforced automatically)
    retry: Dict[str, Any] = field(default_factory=lambda: {
        "max_attempts": 3,
        "initial_backoff_s": 0.5,
        "max_backoff_s": 8.0,
        "multiplier": 2.0,
    })

    # ---------- Loading ----------
    @classmethod
    def load(cls, yaml_path: Path = DEFAULT_YAML) -> "Config":
        y = _load_yaml(yaml_path)

        # 1) Start from YAML
        cfg = cls(
            _source=f"file:{yaml_path}" if y else "defaults",
            project=y.get("project"),
            location=y.get("location"),
            api_endpoint=y.get("api_endpoint"),
            credentials_name=y.get("credentials_name"),
            use_adc=_env_bool("USE_ADC", False),
            llm=LLMDefaults(
                model_name=y.get("model_name", LLMDefaults.model_name),
                temperature=y.get("temperature", LLMDefaults.temperature),
                top_p=y.get("top_p", LLMDefaults.top_p),
                top_k=y.get("top_k", LLMDefaults.top_k),
                candidate_count=y.get("candidate_count", LLMDefaults.candidate_count),
                max_output_tokens=y.get("max_output_tokens", LLMDefaults.max_output_tokens),
                response_mime_type=y.get("response_mime_type", LLMDefaults.response_mime_type),
                system_instruction=y.get("system_instruction", LLMDefaults.system_instruction),
                stop_sequences=y.get("stop_sequences", LLMDefaults.stop_sequences),
                timeout_s=y.get("timeout_s", LLMDefaults.timeout_s),
            ),
            agents=y.get("agents", {}) if isinstance(y.get("agents", {}), dict) else {},
            logging=LoggingDefaults(
                level=(y.get("logging", {}) or {}).get("level", LoggingDefaults.level),
                format=(y.get("logging", {}) or {}).get("format", LoggingDefaults.format),
                include_request_id=(y.get("logging", {}) or {}).get("include_request_id", LoggingDefaults.include_request_id),
                file=(y.get("logging", {}) or {}).get("file", LoggingDefaults.file),
                rotate_mb=(y.get("logging", {}) or {}).get("rotate_mb", LoggingDefaults.rotate_mb),
                rotate_backups=(y.get("logging", {}) or {}).get("rotate_backups", LoggingDefaults.rotate_backups),
            ),
            retry=y.get("retry", {}) or {},
        )

        # 2) Env overrides (highest priority)
        cfg.project = _coalesce_env("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT", default=cfg.project)
        cfg.location = _coalesce_env("GOOGLE_CLOUD_REGION", "GOOGLE_CLOUD_LOCATION", default=cfg.location)
        cfg.api_endpoint = os.getenv("VERTEX_API_ENDPOINT", cfg.api_endpoint)
        # If user points to a direct credentials file via env, prefer that:
        # (typical Google SDK var)
        env_cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if env_cred:
            cfg.credentials_name = env_cred  # absolute path

        # 3) Final sanity
        if not cfg.project or not cfg.location:
            raise RuntimeError("Config missing GCP 'project' or 'location' (YAML or env).")

        return cfg

    # ---------- Auth resolution ----------
    def credential_path(self) -> Optional[Path]:
        """Resolve local credentials file path when USE_ADC=false."""
        if self.use_adc:
            return None
        # If credentials_name looks like an absolute path (from env), use it
        if self.credentials_name and os.path.isabs(self.credentials_name):
            return Path(self.credentials_name)
        # Otherwise resolve from src/.keys/<credentials_name>
        if self.credentials_name:
            keys_dir = Path(__file__).resolve().parents[1] / ".keys"
            candidate = keys_dir / self.credentials_name
            if candidate.exists():
                return candidate
        # No local key => rely on GOOGLE_APPLICATION_CREDENTIALS or ADC
        return None

     # ---------- Google env wiring ----------
    
    def apply_google_env(self) -> None:
        """
        Export env vars for SDKs that read ADC from environment.
        - If use_adc=True: ensure GOOGLE_APPLICATION_CREDENTIALS is unset (SDK will use ADC).
        - Else: set GOOGLE_APPLICATION_CREDENTIALS to the resolved key file path (if any).
        Always set GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_REGION for downstream libs.
        """
        if self.use_adc:
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        else:
            p = self.credential_path()
            if p is not None:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(p.resolve())
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.project or ""
        os.environ["GOOGLE_CLOUD_REGION"] = self.location or ""

    # ---------- Credentials object (for explicit injection) ----------
    def load_credentials(self):
        """
        Returns a google.oauth2.service_account.Credentials object when not using ADC.
        Returns None if use_adc=True or when no local key is configured.
        """
        if self.use_adc:
            return None
        p = self.credential_path()
        if p is None or not p.exists():
            return None
        return _SACredentials.from_service_account_file(
            str(p),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    # ---------- Vertex endpoint bootstrap ----------
    def init_vertex(self, credentials=None) -> None:
        """
        Initialize the Vertex AI client with explicit named parameters.
        Using named args avoids Pylance '**kwargs' type confusion.
        """
        if credentials is None:
            vertexai.init(project=self.project, location=self.location)
        else:
            vertexai.init(project=self.project, location=self.location, credentials=credentials)
        
    # ---------- LLM kwargs builder ----------
    def llm_kwargs(self, agent: Optional[str] = None, **overrides) -> Dict[str, Any]:
        """
        Construct kwargs for your Vertex chat model wrapper.
        - Global defaults
        - merged with per-agent overrides (if any)
        - merged with per-call overrides (**overrides)
        """
        base = {
            "project": self.project,
            "location": self.location,
            "model": self.llm.model_name,
            "temperature": self.llm.temperature,
            "top_p": self.llm.top_p,
            "top_k": int(self.llm.top_k),
            "candidate_count": int(self.llm.candidate_count),
            "max_output_tokens": int(self.llm.max_output_tokens),
            "response_mime_type": self.llm.response_mime_type,
            "system_instruction": self.llm.system_instruction,
            "stop_sequences": list(self.llm.stop_sequences or []),
            "timeout_s": int(self.llm.timeout_s),
            # api_endpoint is optional and only used if your SDK supports it
            "api_endpoint": self.api_endpoint,
        }
        if agent and agent in self.agents:
            # Allow any fields above to be overridden by agent-scoped values
            base.update(self.agents[agent])
        # Runtime overrides win last
        base.update(overrides)
        return base

    # ---------- Retry policy ----------
    def retry_policy(self) -> Dict[str, Any]:
        """
        Return app-level retry policy (for your own wrapper).
        You can implement the actual retry using this info.
        """
        return {
            "max_attempts": int(self.retry.get("max_attempts", 3)),
            "initial_backoff_s": float(self.retry.get("initial_backoff_s", 0.5)),
            "max_backoff_s": float(self.retry.get("max_backoff_s", 8.0)),
            "multiplier": float(self.retry.get("multiplier", 2.0)),
        }

    # ---------- Logging config ----------
    def logging_config(self) -> Dict[str, Any]:
        """
        Produce a logging dict config (or your custom structure) based on YAML.
        Your logging_config.py can consume this to configure handlers/formatters.
        """
        return {
            "level": self.logging.level,
            "format": self.logging.format,
            "include_request_id": bool(self.logging.include_request_id),
            "file": self.logging.file,
            "rotate_mb": int(self.logging.rotate_mb),
            "rotate_backups": int(self.logging.rotate_backups),
            "source": self._source,
        }
