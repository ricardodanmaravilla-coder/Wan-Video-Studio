from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from gradio_client import Client, handle_file
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "app" / "static"
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

WORKER_MODE = os.getenv("WORKER_MODE", "http").strip().lower()
WORKER_URL = os.getenv("WORKER_URL", "http://127.0.0.1:7860").rstrip("/")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "").strip()
HF_SPACE_T2V = os.getenv("HF_SPACE_T2V", "").strip()
HF_SPACE_I2V = os.getenv("HF_SPACE_I2V", "").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
SCENE_SECONDS = 5

app = FastAPI(title="Wan Video Studio", version="0.4.1")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    duration: int = Field(default=30, ge=5, le=30)
    aspect: str = Field(default="16:9")
    style: str = Field(default="cinematic")


def split_story(prompt: str, duration: int, style: str) -> list[str]:
    count = max(1, round(duration / SCENE_SECONDS))
    camera = [
        "wide establishing shot",
        "medium tracking shot",
        "close-up detail shot",
        "dynamic side shot",
        "cinematic low-angle shot",
        "final wide hero shot",
    ]
    return [
        (
            f"{prompt}. Scene {i+1}/{count}. {camera[i % len(camera)]}. "
            f"{style} style. Natural coherent motion. Keep exactly the same main subjects, "
            "face identity, body proportions, wardrobe, colors, props, environment, time of day "
            "and lighting as the previous scene. Avoid abrupt visual changes."
        )
        for i in range(count)
    ]


def extract_last_frame(video: Path, image: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-sseof", "-0.12", "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(image),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg no está instalado o no está en PATH.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"No pude extraer el último frame: {e.stderr.decode(errors='ignore')[-800:]}")


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
        "-movflags", "+faststart", str(output),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        raise HTTPException(500, "FFmpeg no está instalado o no está en PATH.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"FFmpeg falló: {e.stderr.decode(errors='ignore')[-800:]}")


def _resolve_gradio_output(result) -> Path:
    if isinstance(result, str):
        return Path(result)
    if isinstance(result, dict):
        for key in ("path", "name"):
            if result.get(key):
                return Path(result[key])
    if isinstance(result, (list, tuple)) and result:
        return _resolve_gradio_output(result[0])
    raise RuntimeError(f"Salida Gradio no reconocida: {type(result).__name__}")


def _make_gradio_client(space: str) -> Client:
    kwargs = {}
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    return Client(space, **kwargs)


def generate_gradio_scene(prompt: str, aspect: str, reference: Path | None) -> Path:
    space = HF_SPACE_I2V if reference else HF_SPACE_T2V
    if not space:
        needed = "HF_SPACE_I2V" if reference else "HF_SPACE_T2V"
        raise RuntimeError(f"{needed} no está configurado")

    client = _make_gradio_client(space)
    if reference:
        result = client.predict(
            prompt,
            aspect,
            handle_file(str(reference)),
            WORKER_TOKEN,
            api_name="/generate_video",
        )
    else:
        result = client.predict(
            prompt,
            aspect,
            WORKER_TOKEN,
            api_name="/generate_video",
        )

    path = _resolve_gradio_output(result)
    if not path.exists():
        raise RuntimeError("Gradio devolvió un archivo que no existe localmente")
    return path


async def generate_http_scene(
    client: httpx.AsyncClient,
    prompt: str,
    idx: int,
    aspect: str,
    job_id: str,
    reference: Path | None,
) -> bytes:
    reference_b64 = None
    if reference:
        reference_b64 = base64.b64encode(reference.read_bytes()).decode("ascii")
    payload = {
        "prompt": prompt,
        "scene": idx,
        "aspect": aspect,
        "job_id": job_id,
        "reference_image_b64": reference_b64,
    }
    r = await client.post(f"{WORKER_URL}/generate", json=payload)
    r.raise_for_status()
    data = r.json()
    download_url = data.get("download_url")
    if not download_url:
        raise RuntimeError("El worker no devolvió download_url")
    if download_url.startswith("/"):
        download_url = f"{WORKER_URL}{download_url}"
    vr = await client.get(download_url)
    vr.raise_for_status()
    return vr.content


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health():
    if WORKER_MODE == "gradio":
        return {
            "ok": True,
            "worker_mode": "gradio",
            "t2v_space": HF_SPACE_T2V or None,
            "i2v_space": HF_SPACE_I2V or None,
            "configured": bool(HF_SPACE_T2V and HF_SPACE_I2V),
        }
    worker = {"reachable": False}
    try:
        headers = {"Authorization": f"Bearer {WORKER_TOKEN}"} if WORKER_TOKEN else {}
        async with httpx.AsyncClient(timeout=5, headers=headers) as client:
            r = await client.get(f"{WORKER_URL}/health")
            r.raise_for_status()
            worker = {"reachable": True, "details": r.json()}
    except Exception as e:
        worker = {"reachable": False, "error": str(e)}
    return {"ok": True, "worker_mode": "http", "worker_url": WORKER_URL, "worker": worker}


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    job_id = uuid.uuid4().hex[:12]
    job_dir = OUT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes = split_story(req.prompt, req.duration, req.style)
    scene_paths: list[Path] = []
    previous_frame: Path | None = None

    headers = {"Authorization": f"Bearer {WORKER_TOKEN}"} if WORKER_TOKEN else {}
    async with httpx.AsyncClient(timeout=1800, headers=headers) as http_client:
        for idx, scene_prompt in enumerate(scenes, start=1):
            local_path = job_dir / f"scene_{idx:02d}.mp4"
            try:
                if WORKER_MODE == "gradio":
                    remote_file = await asyncio.to_thread(
                        generate_gradio_scene,
                        scene_prompt,
                        req.aspect,
                        previous_frame,
                    )
                    shutil.copy2(remote_file, local_path)
                else:
                    content = await generate_http_scene(
                        http_client,
                        scene_prompt,
                        idx,
                        req.aspect,
                        job_id,
                        previous_frame,
                    )
                    local_path.write_bytes(content)
            except Exception as e:
                raise HTTPException(502, f"Worker GPU falló en escena {idx}: {e}")

            scene_paths.append(local_path)
            if idx < len(scenes):
                previous_frame = job_dir / f"scene_{idx:02d}_last.jpg"
                extract_last_frame(local_path, previous_frame)

    final_path = job_dir / "final.mp4"
    concat_videos(scene_paths, final_path)
    return {
        "job_id": job_id,
        "scenes": len(scenes),
        "continuity": len(scenes) > 1,
        "worker_mode": WORKER_MODE,
        "video_url": f"/api/video/{job_id}",
    }


@app.get("/api/video/{job_id}")
def video(job_id: str):
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    path = OUT / safe / "final.mp4"
    if not path.exists():
        raise HTTPException(404, "Video no encontrado")
    return FileResponse(path, media_type="video/mp4", filename=f"wan-{safe}.mp4")
