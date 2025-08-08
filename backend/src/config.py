from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from google.oauth2.service_account import Credentials
from google.oauth2.service_account import Credentials

USE_ADC = os.getenv("USE_ADC", "false").lower() == "true" # for local testing， in later deployment, ADC will be seet and used
BASE_DIR = Path(__file__).resolve().parent  # == <repo>/src

# TODO: implement ADC, now is fixed for local testing
@dataclass(frozen=True)
class Config:
    project: str = "aime-hello-world"
    location: str = "us-central1"
    credentials_path: Path = BASE_DIR / ".keys" / "aime-hello-world-2cd68fc662f2.json"
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.2
    max_output_tokens: int = 512

    def apply_google_credentials(self) -> None:
        # Write ADC environment variables only in "local explicit credential" mode; do not write in cloud ADC mode.
        if not USE_ADC:
            cred_abs = str(self.credentials_path.resolve())
            if not self.credentials_path.exists():
                raise FileNotFoundError(f"Service account key not found at: {cred_abs}")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_abs
            os.environ["GOOGLE_CLOUD_PROJECT"] = self.project
            os.environ["GOOGLE_CLOUD_REGION"] = self.location

    def load_credentials(self) -> Credentials:
        cred_abs = str(self.credentials_path.resolve())
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"Service account key not found at: {cred_abs}")
        return Credentials.from_service_account_file(
            cred_abs, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )