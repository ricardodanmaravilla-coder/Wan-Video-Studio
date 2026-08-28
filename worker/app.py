from __future__ import annotations

import os
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .mock_engine import generate_mock
from .wan_engine import generate_wan

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "worker_outputs"
OUT.mkdir(exist_ok=True)

MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"

app = FastAPI(title="Wan GPU Worker", version="0.1.0")


class Request(BaseModel):
    prompt: str
    scene: int = 1
    aspect: str = "16:9"
    job_id: str = ""


@app.get("/health")
def health():
    return {"ok": True, "mock": MOCK_MODE}


@app.post("/generate")
def generate(req: Request):
    name = f"{req.job_id or uuid.uuid4().hex[:8]}_{req.scene:02d}.mp4"
    out = OUT / name

    try:
        if MOCK_MODE:
            generate_mock(req.prompt, out, req.aspect)
        else:
            generate_wan(req.prompt, out, req.aspect)
    except Exception as e:
        raise HTTPException(500, str(e))

    return {"ok": True, "path": str(out.resolve())}
