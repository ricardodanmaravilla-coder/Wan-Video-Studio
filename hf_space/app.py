import gc
import os
import tempfile
from pathlib import Path

import spaces
import gradio as gr
import torch
from PIL import Image
from diffusers import UniPCMultistepScheduler, WanImageToVideoPipeline, WanPipeline
from diffusers.utils import export_to_video

MODEL_ID = os.getenv("WAN_MODEL_ID", "yetter-ai/Wan2.2-TI2V-5B-Turbo-Diffusers")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "")
NUM_FRAMES = int(os.getenv("WAN_NUM_FRAMES", "121"))
FPS = int(os.getenv("WAN_FPS", "24"))
STEPS = int(os.getenv("WAN_STEPS", "4"))
SEED = int(os.getenv("WAN_SEED", "43"))

# Se inicia en T2V. ZeroGPU permite colocar el modelo en cuda fuera del decorador.
active_mode = "t2v"
pipe = WanPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=5.0)
pipe.to("cuda")


def _dims(aspect: str):
    if aspect == "9:16":
        return 704, 1280
    if aspect == "1:1":
        return 960, 960
    return 1280, 704


def _check_token(token: str):
    if WORKER_TOKEN and token != WORKER_TOKEN:
        raise gr.Error("Worker token inválido")


def _switch_to_i2v():
    global pipe, active_mode
    if active_mode == "i2v":
        return pipe

    try:
        pipe.to("cpu")
    except Exception:
        pass
    del pipe
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    pipe = WanImageToVideoPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=5.0)
    pipe.to("cuda")
    active_mode = "i2v"
    return pipe


@spaces.GPU(duration=120, size="large")
def generate_video(prompt: str, aspect: str, reference_image, token: str):
    global pipe, active_mode
    _check_token(token)
    width, height = _dims(aspect)
    generator = torch.Generator(device="cuda").manual_seed(SEED)

    if reference_image is not None:
        current_pipe = _switch_to_i2v()
        image = Image.open(reference_image).convert("RGB")
        image = image.resize((width, height))
        result = current_pipe(
            image=image,
            prompt=prompt,
            height=height,
            width=width,
            num_frames=NUM_FRAMES,
            num_inference_steps=STEPS,
            guidance_scale=1.0,
            generator=generator,
        ).frames[0]
    else:
        if active_mode != "t2v":
            raise gr.Error(
                "Este worker ya cambió a modo continuidad I2V. Reinicia el Space para iniciar un proyecto T2V nuevo."
            )
        result = pipe(
            prompt=prompt,
            height=height,
            width=width,
            num_frames=NUM_FRAMES,
            num_inference_steps=STEPS,
            guidance_scale=1.0,
            generator=generator,
        ).frames[0]

    out = Path(tempfile.mkdtemp()) / "scene.mp4"
    export_to_video(result, str(out), fps=FPS)
    return str(out)


with gr.Blocks(title="Wan Video Studio GPU Worker") as demo:
    gr.Markdown("# Wan Video Studio · ZeroGPU Worker")
    gr.Markdown("Wan 2.2 TI2V-5B Turbo · 121 frames · 24 FPS · 4 pasos")
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
