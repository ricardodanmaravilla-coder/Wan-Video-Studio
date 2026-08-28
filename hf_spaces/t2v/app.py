import os
import tempfile
from pathlib import Path

import spaces
import gradio as gr
import torch
from diffusers import UniPCMultistepScheduler, WanPipeline
from diffusers.utils import export_to_video

MODEL_ID = os.getenv("WAN_MODEL_ID", "yetter-ai/Wan2.2-TI2V-5B-Turbo-Diffusers")
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "")
NUM_FRAMES = int(os.getenv("WAN_NUM_FRAMES", "121"))
FPS = int(os.getenv("WAN_FPS", "24"))
STEPS = int(os.getenv("WAN_STEPS", "4"))
SEED = int(os.getenv("WAN_SEED", "43"))

pipe = WanPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=5.0)
pipe.to("cuda")


def dims(aspect: str):
    if aspect == "9:16":
        return 704, 1280
    if aspect == "1:1":
        return 960, 960
    return 1280, 704


@spaces.GPU(duration=120, size="large")
def generate_video(prompt: str, aspect: str, token: str):
    if WORKER_TOKEN and token != WORKER_TOKEN:
        raise gr.Error("Worker token inválido")
    width, height = dims(aspect)
    generator = torch.Generator(device="cuda").manual_seed(SEED)
    video = pipe(
        prompt=prompt,
        width=width,
        height=height,
        num_frames=NUM_FRAMES,
        num_inference_steps=STEPS,
        guidance_scale=1.0,
        generator=generator,
    ).frames[0]
    out = Path(tempfile.mkdtemp()) / "scene.mp4"
    export_to_video(video, str(out), fps=FPS)
    return str(out)


with gr.Blocks(title="Wan Video Studio T2V Worker") as demo:
    gr.Markdown("# Wan Video Studio · T2V ZeroGPU")
    prompt = gr.Textbox(label="Prompt", lines=5)
    aspect = gr.Dropdown(["16:9", "9:16", "1:1"], value="16:9", label="Formato")
    token = gr.Textbox(label="Worker token", type="password")
    button = gr.Button("Generar")
    output = gr.Video(label="Video")
    button.click(generate_video, [prompt, aspect, token], output, api_name="generate_video")

demo.queue(max_size=8).launch()
