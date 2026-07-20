"""FastAPI tool server for Google Docs + Gmail.

This is the REST entrypoint the upstream MCP repo (ArpitDumka/Google-mcp-server)
does not ship — it only has the Streamlit UI (`app.py`). The weekly GitHub
Actions job checks out that repo, overlays this file, and runs it with
`uvicorn server:app` so Phase 4 can call the tools over HTTP.

Keep this in sync with the copy used for local delivery.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from docs_tool import append_to_doc
from gmail_tool import create_email_draft
from fastapi import FastAPI

app = FastAPI(title="Google MCP Server", version="1.0.0")


class AppendToDocRequest(BaseModel):
    doc_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class CreateEmailDraftRequest(BaseModel):
    to: str = Field(min_length=3)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/append_to_doc")
def append_to_doc_endpoint(payload: AppendToDocRequest) -> dict:
    return append_to_doc(payload.doc_id, payload.content)


@app.post("/create_email_draft")
def create_email_draft_endpoint(payload: CreateEmailDraftRequest) -> dict:
    return create_email_draft(payload.to, payload.subject, payload.body)
