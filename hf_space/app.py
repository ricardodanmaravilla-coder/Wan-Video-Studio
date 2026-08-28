import os
import tempfile
from pathlib import Path

import spaces
import gradio as gr
import torch
from PIL import Image
from diffusers import WanPipeline, WanImageToVideoPipeline
from diffusers.utils import export_to_video

MODEL_ID = os.getenv("WAN_MODEL_ID", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "")
NUM_FRAMES = int(os.getenv("WAN_NUM_FRAMES", "121"))
FPS = int(os.getenv("WAN_FPS", "24"))
STEPS = int(os.getenv("WAN_STEPS", "20"))

# ZeroGPU emula CUDA fuera de @spaces.GPU, como recomienda Hugging Face.
t2v_pipe = WanPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
t2v_pipe.enable_model_cpu_offload()

i2v_pipe = None


def _dims(aspect: str):
    if aspect == "9:16":
        return 704, 1280
    if aspect == "1:1":
        return 960, 960
    return 1280, 704


def _check_token(token: str):
    if WORKER_TOKEN and token != WORKER_TOKEN:
        raise gr.Error("Worker token inválido")


def _get_i2v_pipe():
    global i2v_pipe
    if i2v_pipe is None:
        i2v_pipe = WanImageToVideoPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
        )
        i2v_pipe.enable_model_cpu_offload()
    return i2v_pipe


@spaces.GPU(duration=300, size="large")
def generate_video(prompt: str, aspect: str, reference_image, token: str):
    _check_token(token)
    width, height = _dims(aspect)

    negative_prompt = (
        "low quality, blurry, distorted face, deformed hands, duplicate people, "
        "flicker, abrupt scene change, subtitles, watermark, text"
    )

    if reference_image is not None:
        pipe = _get_i2v_pipe()
        image = Image.open(reference_image).convert("RGB")
        result = pipe(
            image=image,
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=height,
            width=width,
            num_frames=NUM_FRAMES,
            num_inference_steps=STEPS,
            guidance_scale=5.0,
        ).frames[0]
    else:
        result = t2v_pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=height,
            width=width,
            num_frames=NUM_FRAMES,
            num_inference_steps=STEPS,
            guidance_scale=5.0,
        ).frames[0]

    out = Path(tempfile.mkdtemp()) / "scene.mp4"
    export_to_video(result, str(out), fps=FPS)
    return str(out)


with gr.Blocks(title="Wan Video Studio GPU Worker") as demo:
    gr.Markdown("# Wan Video Studio · ZeroGPU Worker")
    gr.Markdown("Worker GPU para la aplicación principal. Genera una escena por solicitud.")
    prompt = gr.Textbox(label="Prompt", lines=5)
    aspect = gr.Dropdown(["16:9", "9:16", "1:1"], value="16:9", label="Formato")
    reference = gr.Image(type="filepath", label="Frame de continuidad", sources=["upload"])
    token = gr.Textbox(label="Worker token", type="password")
    button = gr.Button("Generar escena")
    output = gr.Video(label="Resultado")
    button.click(
        generate_video,
        inputs=[prompt, aspect, reference, token],
        outputs=output,
        api_name="generate_video",
    )

demo.queue(max_size=8).launch()
