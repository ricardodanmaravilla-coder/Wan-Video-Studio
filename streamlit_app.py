from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
from gradio_client import Client, handle_file

SCENE_SECONDS = 5
DEFAULT_T2V = "RicasMaravilla/wan-video-studio-t2v"
DEFAULT_I2V = "RicasMaravilla/wan-video-studio-i2v"

st.set_page_config(
    page_title="Wan Video Studio",
    page_icon="🎬",
    layout="wide",
)


def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or "").strip()


def split_story(prompt: str, duration: int, style: str) -> list[str]:
    count = max(1, round(duration / SCENE_SECONDS))
    cameras = [
        "wide establishing shot",
        "medium tracking shot",
        "close-up detail shot",
        "dynamic side shot",
        "cinematic low-angle shot",
        "final wide hero shot",
    ]
    scenes = []
    for i in range(count):
        continuity = (
            "Maintain exactly the same main subjects, face identity, body proportions, "
            "wardrobe, colors, props, environment, time of day and lighting. "
            "Continue naturally from the previous scene without abrupt changes."
            if i > 0
            else "Establish a clear consistent subject, wardrobe, environment and lighting for all following scenes."
        )
        scenes.append(
            f"{prompt}. Scene {i + 1}/{count}. {cameras[i % len(cameras)]}. "
            f"{style} style. Natural coherent motion. {continuity}"
        )
    return scenes


def resolve_output(result) -> Path:
    """Find a local output file in current and nested Gradio response formats."""
    if isinstance(result, Path):
        return result

    if isinstance(result, str):
        return Path(result)

    if isinstance(result, dict):
        # Prefer the common Gradio FileData fields first.
        for key in ("path", "name"):
            value = result.get(key)
            if isinstance(value, (str, Path)) and value:
                return Path(value)

        # Newer Gradio versions can wrap FileData in video/value/data containers.
        preferred = ("video", "value", "data", "file", "output")
        for key in preferred:
            if key in result:
                try:
                    return resolve_output(result[key])
                except RuntimeError:
                    pass

        # Last resort: recursively inspect every nested value.
        for value in result.values():
            try:
                return resolve_output(value)
            except RuntimeError:
                continue

    if isinstance(result, (list, tuple)):
        for item in result:
            try:
                return resolve_output(item)
            except RuntimeError:
                continue

    raise RuntimeError(
        f"Salida de Gradio no reconocida: {type(result).__name__}. "
        f"Estructura: {repr(result)[:500]}"
    )


def extract_last_frame(video: Path, image: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-sseof", "-0.12", "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(image),
    ]
    completed = subprocess.run(cmd, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "FFmpeg no pudo extraer el frame de continuidad: "
            + completed.stderr.decode(errors="ignore")[-700:]
        )


def concat_videos(paths: list[Path], output: Path) -> None:
    concat_file = output.with_suffix(".txt")
    concat_file.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in paths),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]
    completed = subprocess.run(cmd, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "FFmpeg no pudo unir las escenas: "
            + completed.stderr.decode(errors="ignore")[-700:]
        )


def make_client(space: str, hf_token: str | None) -> Client:
    kwargs = {"verbose": False}
    if hf_token:
        kwargs["token"] = hf_token
    return Client(space, **kwargs)


def generate_scene(
    prompt: str,
    aspect: str,
    reference: Path | None,
    worker_token: str,
    hf_token: str | None,
) -> Path:
    space = secret("HF_SPACE_I2V", DEFAULT_I2V) if reference else secret("HF_SPACE_T2V", DEFAULT_T2V)
    client = make_client(space, hf_token)

    if reference:
        result = client.predict(
            prompt,
            aspect,
            handle_file(str(reference)),
            worker_token,
            api_name="/generate_video",
        )
    else:
        result = client.predict(
            prompt,
            aspect,
            worker_token,
            api_name="/generate_video",
        )

    output = resolve_output(result)
    if not output.exists():
        raise RuntimeError(f"Hugging Face devolvió un archivo que no existe localmente: {output}")
    return output


def run_generation(prompt: str, duration: int, aspect: str, style: str) -> tuple[bytes, int]:
    worker_token = secret("WORKER_TOKEN")
    hf_token = secret("HF_TOKEN") or None
    if not worker_token:
        raise RuntimeError("Falta WORKER_TOKEN en los Secrets de Streamlit.")

    scenes = split_story(prompt, duration, style)
    progress = st.progress(0, text="Preparando generación…")
    status = st.empty()

    with tempfile.TemporaryDirectory(prefix="wan-studio-") as tmp:
        work = Path(tmp)
        scene_paths: list[Path] = []
        reference: Path | None = None

        for idx, scene_prompt in enumerate(scenes, start=1):
            status.info(f"Generando escena {idx} de {len(scenes)} en ZeroGPU…")
            remote_video = generate_scene(
                scene_prompt,
                aspect,
                reference,
                worker_token,
                hf_token,
            )
            local_video = work / f"scene_{idx:02d}.mp4"
            shutil.copy2(remote_video, local_video)
            scene_paths.append(local_video)

            if idx < len(scenes):
                reference = work / f"scene_{idx:02d}_last.jpg"
                extract_last_frame(local_video, reference)

            progress.progress(
                idx / len(scenes),
                text=f"Escena {idx}/{len(scenes)} completada",
            )

        status.info("Uniendo escenas con FFmpeg…")
        final = work / "wan_video_final.mp4"
        concat_videos(scene_paths, final)
        data = final.read_bytes()

    progress.progress(1.0, text="Video terminado")
    status.success("Generación completada")
    return data, len(scenes)


st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 2rem;}
    div[data-testid="stMetric"] {background: rgba(120,120,120,.08); padding: 14px; border-radius: 14px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎬 Wan Video Studio")
st.caption("Generación de video con Wan 2.2 + Hugging Face ZeroGPU · continuidad automática entre escenas")

with st.sidebar:
    st.subheader("Configuración")
    duration = st.select_slider("Duración", options=[5, 10, 15, 20, 25, 30], value=10, format_func=lambda x: f"{x} s")
    aspect = st.selectbox("Formato", ["16:9", "9:16", "1:1"], index=0)
    style = st.selectbox(
        "Estilo",
        ["cinematic", "realistic", "commercial", "documentary", "anime"],
        index=0,
    )
    st.divider()
    st.caption("Para pruebas iniciales recomiendo 5 s. Los videos largos consumen varias llamadas a ZeroGPU.")

prompt = st.text_area(
    "Describe el video",
    height=160,
    placeholder="Ejemplo: Un automóvil deportivo rojo recorriendo una carretera de montaña al amanecer, cámara cinematográfica…",
)

generate = st.button("✨ Generar video", type="primary", use_container_width=True)

if generate:
    if len(prompt.strip()) < 3:
        st.error("Escribe una descripción del video.")
    else:
        try:
            video_bytes, scene_count = run_generation(prompt.strip(), duration, aspect, style)
            st.session_state["wan_video"] = video_bytes
            st.session_state["wan_scene_count"] = scene_count
        except Exception as exc:
            st.error(f"La generación falló: {exc}")

if "wan_video" in st.session_state:
    st.subheader("Resultado")
    st.video(st.session_state["wan_video"], format="video/mp4")
    c1, c2, c3 = st.columns(3)
    c1.metric("Duración objetivo", f"{duration} s")
    c2.metric("Escenas", st.session_state.get("wan_scene_count", 1))
    c3.metric("Continuidad", "I2V activa" if st.session_state.get("wan_scene_count", 1) > 1 else "T2V")
    st.download_button(
        "⬇️ Descargar MP4",
        data=st.session_state["wan_video"],
        file_name="wan-video-studio.mp4",
        mime="video/mp4",
        use_container_width=True,
    )
