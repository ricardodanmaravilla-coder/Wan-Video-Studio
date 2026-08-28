from __future__ import annotations

import os
import uuid
import shutil
import subprocess
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "app" / "static"
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

WORKER_URL = os.getenv("WORKER_URL", "http://127.0.0.1:7860").rstrip("/")

app = FastAPI(title="Wan Video Studio", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    duration: int = Field(default=30, ge=5, le=30)
    aspect: str = Field(default="16:9")
    style: str = Field(default="cinematic")


def split_story(prompt: str, duration: int, style: str) -> list[str]:
    count = max(1, round(duration / 5))
    camera = [
        "wide establishing shot",
        "medium tracking shot",
        "close-up detail shot",
        "dynamic side shot",
        "cinematic low-angle shot",
        "final wide hero shot",
    ]
    scenes = []
    for i in range(count):
        scenes.append(
            f"{prompt}. Scene {i+1}/{count}. {camera[i % len(camera)]}. "
            f"{style} style. Natural coherent motion. Maintain the same subjects, "
            f"wardrobe, colors, environment and lighting continuity."
        )
    return scenes


def concat_videos(paths: list[Path], output: Path) -> None:
    list_file = output.with_suffix(".txt")
    list_file.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in paths),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg no está instalado o no está en PATH.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"FFmpeg falló: {e.stderr.decode(errors='ignore')[-800:]}")


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "worker": WORKER_URL}


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    job_id = uuid.uuid4().hex[:12]
    job_dir = OUT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    scenes = split_story(req.prompt, req.duration, req.style)
    scene_paths: list[Path] = []

    async with httpx.AsyncClient(timeout=1800) as client:
        for idx, scene_prompt in enumerate(scenes, start=1):
            payload = {
                "prompt": scene_prompt,
                "scene": idx,
                "aspect": req.aspect,
                "job_id": job_id,
            }
            try:
                r = await client.post(f"{WORKER_URL}/generate", json=payload)
                r.raise_for_status()
            except Exception as e:
                raise HTTPException(502, f"Worker GPU falló en escena {idx}: {e}")

            data = r.json()
            remote_path = Path(data["path"])
            if not remote_path.exists():
                raise HTTPException(
                    502,
                    "El worker respondió, pero el archivo no es accesible desde este host. "
                    "En despliegue remoto se cambiará por descarga HTTP/objeto storage."
                )
            local_path = job_dir / f"scene_{idx:02d}.mp4"
            shutil.copy2(remote_path, local_path)
            scene_paths.append(local_path)

    final_path = job_dir / "final.mp4"
    concat_videos(scene_paths, final_path)

    return {
        "job_id": job_id,
        "scenes": len(scenes),
        "video_url": f"/api/video/{job_id}",
    }


@app.get("/api/video/{job_id}")
def video(job_id: str):
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    path = OUT / safe / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "Video no encontrado")
    return FileResponse(path, media_type="video/mp4", filename=f"wan-{safe}.mp4")
