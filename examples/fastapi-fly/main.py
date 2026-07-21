"""Minimal FastAPI app calling Celeris server-side.

The browser talks only to THIS app; the Celeris API key comes from the
environment, locally from your shell, in production from Fly.io's encrypted
secret store (`fly secrets set`), and never reaches the client.

    export CELERIS_BASE_URL="https://<your-celeris-endpoint>"
    export CELERIS_API_KEY="<your-api-key>"
    uvicorn main:app --reload
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Celeris on FastAPI")
STATIC = Path(__file__).resolve().parent / "static"


def celeris_base_url() -> str:
    """CELERIS_BASE_URL is the endpoint root (no /v1); the OpenAI SDK wants
    the versioned path, so append /v1 unless it is already there."""
    base = (
        os.environ.get("CELERIS_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def normalize_max_tokens(requested: int) -> int:
    """Celeris accepts max_tokens only as a multiple of 256 in [256, 1024],
    inside a 4096-token total window shared with the input."""
    return min(max(-(-requested // 256) * 256, 256), 1024)


class GenerateRequest(BaseModel):
    prompt: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/api/generate")
def generate(request: GenerateRequest) -> dict:
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt required")

    api_key = os.environ.get("CELERIS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key or not os.environ.get("CELERIS_BASE_URL"):
        raise HTTPException(
            status_code=500, detail="server missing CELERIS_BASE_URL / CELERIS_API_KEY"
        )

    client = OpenAI(base_url=celeris_base_url(), api_key=api_key)
    try:
        completion = client.chat.completions.create(
            model=os.environ.get("CELERIS_MODEL", "celeris-1"),
            messages=[{"role": "user", "content": prompt[:8000]}],
            max_tokens=normalize_max_tokens(512),
            temperature=0.3,
        )
    except Exception as error:  # noqa: BLE001 - single boundary to the upstream
        raise HTTPException(status_code=502, detail="upstream request failed") from error

    return {"reply": completion.choices[0].message.content or ""}
