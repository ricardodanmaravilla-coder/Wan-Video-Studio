from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .mock_engine import generate_mock
from .wan_engine import generate_wan

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "worker_outputs"
OUT.mkdir(exist_ok=True)

MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "").strip()

app = FastAPI(title="Wan GPU Worker", version="0.2.0")


class Request(BaseModel):
    prompt: str
    scene: int = 1
    aspect: str = "16:9"
    job_id: str = ""
    reference_image_b64: str | None = None


def require_token(authorization: str | None) -> None:
    if not WORKER_TOKEN:
        return
    if authorization != f"Bearer {WORKER_TOKEN}":
        raise HTTPException(401, "Worker token inválido")


def safe_name(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in "-_.")
    if not cleaned or cleaned != name:
        raise HTTPException(400, "Nombre de archivo inválido")
    return cleaned


@app.get("/health")
def health():
    return {"ok": True, "mock": MOCK_MODE, "auth": bool(WORKER_TOKEN)}


@app.post("/generate")
def generate(req: Request, authorization: str | None = Header(default=None)):
    require_token(authorization)

    job = "".join(c for c in (req.job_id or uuid.uuid4().hex[:8]) if c.isalnum() or c in "-_")
    name = f"{job}_{req.scene:02d}.mp4"
    out = OUT / name

    reference_image: Path | None = None
    if req.reference_image_b64:
        reference_image = OUT / f"{job}_{req.scene:02d}_reference.jpg"
        try:
            reference_image.write_bytes(base64.b64decode(req.reference_image_b64, validate=True))
        except Exception as e:
            raise HTTPException(400, f"Imagen de referencia inválida: {e}")

    try:
        if MOCK_MODE:
            generate_mock(req.prompt, out, req.aspect)
        else:
            generate_wan(req.prompt, out, req.aspect, reference_image=reference_image)
    except Exception as e:
        raise HTTPException(500, str(e))

    return {
        "ok": True,
        "scene": req.scene,
        "used_reference_image": reference_image is not None,
        "download_url": f"/files/{name}",
    }


@app.get("/files/{name}")
def files(name: str, authorization: str | None = Header(default=None)):
    require_token(authorization)
    filename = safe_name(name)
    path = OUT / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Clip no encontrado")
    return FileResponse(path, media_type="video/mp4", filename=filename)
