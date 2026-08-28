from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

WAN_REPO = Path(os.getenv("WAN_REPO", "./Wan2.2")).resolve()
WAN_CKPT = Path(os.getenv("WAN_CKPT", "./Wan2.2-TI2V-5B")).resolve()
WAN_SIZE = os.getenv("WAN_SIZE", "1280*704")


def generate_wan(
    prompt: str,
    output: Path,
    aspect: str = "16:9",
    reference_image: Path | None = None,
):
    if not (WAN_REPO / "generate.py").exists():
        raise RuntimeError(f"No encuentro generate.py en WAN_REPO={WAN_REPO}")
    if not WAN_CKPT.exists():
        raise RuntimeError(f"No encuentro WAN_CKPT={WAN_CKPT}")
    if reference_image is not None and not reference_image.exists():
        raise RuntimeError(f"No encuentro la imagen de referencia: {reference_image}")

    size = WAN_SIZE
    if aspect == "9:16":
        size = "704*1280"
    elif aspect == "16:9":
        size = "1280*704"

    before = set(WAN_REPO.rglob("*.mp4"))

    cmd = [
        "python", "generate.py",
        "--task", "ti2v-5B",
        "--size", size,
        "--ckpt_dir", str(WAN_CKPT),
        "--offload_model", "True",
        "--convert_model_dtype",
        "--t5_cpu",
        "--prompt", prompt,
    ]

    # TI2V-5B usa T2V sin --image y cambia a I2V cuando recibe --image.
    # Usamos el último frame de la escena anterior como ancla de continuidad.
    if reference_image is not None:
        cmd.extend(["--image", str(reference_image.resolve())])

    p = subprocess.run(cmd, cwd=str(WAN_REPO), text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("Wan falló:\n" + p.stderr[-2500:])

    after = set(WAN_REPO.rglob("*.mp4"))
    created = list(after - before)
    if not created:
        created = sorted(
            WAN_REPO.rglob("*.mp4"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )[:1]
    if not created:
        raise RuntimeError("Wan terminó pero no encontré ningún MP4 generado.")

    src = max(created, key=lambda x: x.stat().st_mtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, output)
