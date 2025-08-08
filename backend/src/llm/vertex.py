# src/llm/vertex.py
from __future__ import annotations
from typing import Optional
import vertexai
from google.oauth2.service_account import Credentials as SACredentials
from langchain_google_vertexai import ChatVertexAI
from ..config import Config, USE_ADC

def get_vertex_chat_model(cfg: Config) -> ChatVertexAI:
    creds: Optional[SACredentials] = None

    if USE_ADC:
       # Cloud / ADC configured: Do not transmit credentials
        vertexai.init(project=cfg.project, location=cfg.location)
        return ChatVertexAI(
            project=cfg.project,
            location=cfg.location,
            model=cfg.model_name,                 # e.g. "gemini-2.0-flash"
            response_mime_type="text/plain",
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_output_tokens,
            max_retries=6,
        )

    # Local: Explicitly load the service account and pass it in.
    creds = cfg.load_credentials()
    vertexai.init(project=cfg.project, location=cfg.location, credentials=creds)
    return ChatVertexAI(
        project=cfg.project,
        location=cfg.location,
        model=cfg.model_name,
        response_mime_type="text/plain",
        temperature=cfg.temperature,
        max_output_tokens=cfg.max_output_tokens,
        max_retries=6,
        credentials=creds,                      
    )
