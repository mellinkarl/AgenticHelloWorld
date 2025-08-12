from __future__ import annotations

import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import vertexai
import yaml
from google.oauth2.service_account import Credentials
from google.auth import default as google_auth_default
from google.auth.exceptions import DefaultCredentialsError

# ---- Global switches ----
USE_ADC = os.getenv("USE_ADC", "false").lower() == "true"     # prefer ADC if true & available
BASE_DIR = Path(__file__).resolve().parent.parent             # <repo>/src
DEFAULT_YAML = BASE_DIR / "config" / "default.yaml"           # src/config/default.yaml
DEFAULT_KEYS_DIR = BASE_DIR / ".keys"                         # src/.keys/


def _load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        return yaml.safe_load(text) or {}
    except Exception as e:
        raise ValueError(f"Failed to parse config file: {path} ({e})") from e


@dataclass
class LLMDefaults:
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.2
    max_output_tokens: int = 512
    response_mime_type: str = "text/plain"


@dataclass
class LoggingDefaults:
    level: str = "INFO"           # DEBUG/INFO/WARN/ERROR
    format: str = "json"          # json | pretty
    file: Optional[str] = "logs/app.log"  # set None to disable file output
    rotate_mb: int = 10
    rotate_backups: int = 5


@dataclass
class Config:
    # Cloud project/region (from yaml or env)
    project: Optional[str] = None
    location: Optional[str] = None
    # Optional explicit Vertex endpoint override (rarely needed)
    api_endpoint: Optional[str] = None

    # Credentials strategy
    credentials_name: Optional[str] = None  # e.g., "svc.json" under src/.keys/

    # Global LLM defaults
    llm: LLMDefaults = field(default_factory=LLMDefaults)

    # Agent-level overrides, e.g. {"runner": {"model": "...", "temperature": 0.0}}
    agents: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Logging
    logging: LoggingDefaults = field(default_factory=LoggingDefaults)

    # Debug source
    _source: str = "defaults"

    @classmethod
    def load(cls, yaml_path: Path = DEFAULT_YAML) -> "Config":
        y = _load_config(yaml_path)
        cfg = cls(
            project=y.get("project"),
            location=y.get("location"),
            api_endpoint=y.get("api_endpoint"),
            credentials_name=y.get("credentials_name"),
            llm=LLMDefaults(
                model_name=y.get("model_name", LLMDefaults.model_name),
                temperature=y.get("temperature", LLMDefaults.temperature),
                max_output_tokens=y.get("max_output_tokens", LLMDefaults.max_output_tokens),
                response_mime_type=y.get("response_mime_type", LLMDefaults.response_mime_type),
            ),
            agents=y.get("agents", {}) if isinstance(y.get("agents", {}), dict) else {},
            logging=LoggingDefaults(
                level=(y.get("logging", {}) or {}).get("level", LoggingDefaults.level),
                format=(y.get("logging", {}) or {}).get("format", LoggingDefaults.format),
                file=(y.get("logging", {}) or {}).get("file", LoggingDefaults.file),
                rotate_mb=int((y.get("logging", {}) or {}).get("rotate_mb", LoggingDefaults.rotate_mb)),
                rotate_backups=int((y.get("logging", {}) or {}).get("rotate_backups", LoggingDefaults.rotate_backups)),
            ),
            _source=f"file:{yaml_path}" if y else "defaults",
        )

        # Env overrides (highest precedence)
        cfg.project = os.getenv("GOOGLE_CLOUD_PROJECT", cfg.project)
        cfg.location = os.getenv("GOOGLE_CLOUD_REGION", cfg.location)
        cfg.api_endpoint = os.getenv("VERTEX_API_ENDPOINT", cfg.api_endpoint)

        if not cfg.project or not cfg.location:
            raise ValueError(
                "Project/location not set. Provide via src/config/default.yaml or env "
                "[GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_REGION]."
            )
        return cfg

    # ---------- Auth mode selection ----------
    def _adc_is_available(self) -> bool:
        """
        Try to resolve ADC. We don't make any network calls; google.auth.default()
        will use env, GCE/GKE metadata if present.
        """
        try:
            creds, _ = google_auth_default()
            return creds is not None
        except DefaultCredentialsError:
            return False

    def resolve_credentials_path(self) -> Optional[Path]:
        """Local service-account json path when not using valid ADC."""
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
        # Nothing configured
        return None

    def choose_auth_mode(self) -> str:
        """
        'adc' if USE_ADC and ADC can be resolved; otherwise 'local' if we have a key;
        else raise with a helpful message.
        """
        if USE_ADC and self._adc_is_available():
            return "adc"
        cred_path = self.resolve_credentials_path()
        if cred_path:
            return "local"
        raise RuntimeError(
            "No valid auth found. Either set USE_ADC=true with a working ADC environment, "
            "or provide a local service account key (GOOGLE_APPLICATION_CREDENTIALS or credentials_name in default.yaml)."
        )

    def apply_google_env(self) -> None:
        """Export env vars based on chosen auth mode."""
        mode = self.choose_auth_mode()
        if mode == "adc":
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        else:
            cred_path = self.resolve_credentials_path()
            if not cred_path:
                raise FileNotFoundError("Local credentials not found.")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.project or ""
        os.environ["GOOGLE_CLOUD_REGION"] = self.location or ""
        if self.api_endpoint:
            os.environ["VERTEX_API_ENDPOINT"] = self.api_endpoint

    def load_credentials(self) -> Optional[Credentials]:
        """Explicit SA credentials when in 'local' mode, else None for ADC."""
        if self.choose_auth_mode() == "adc":
            return None
        cred_path = self.resolve_credentials_path()
        if not cred_path:
            raise FileNotFoundError("Local credentials not found.")
        return Credentials.from_service_account_file(
            str(cred_path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    # ---------- LLM helpers ----------
    def llm_kwargs(self, agent: Optional[str] = None, **overrides) -> Dict[str, Any]:
        base = {
            "project": self.project,
            "location": self.location,
            "model": self.llm.model_name,
            "temperature": self.llm.temperature,
            "max_output_tokens": int(self.llm.max_output_tokens),
            "response_mime_type": self.llm.response_mime_type,
        }
        if agent and agent in self.agents:
            base.update(self.agents[agent])
        base.update(overrides)
        return base

    def init_vertex(self) -> None:
        vertexai.init(project=self.project, location=self.location)

    # Debug dump
    def debug_print(self) -> None:
        d = asdict(self)
        d.pop("_source", None)
        print(json.dumps(d, ensure_ascii=False, indent=2))
