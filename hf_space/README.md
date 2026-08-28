---
title: Wan Video Studio ZeroGPU Worker
emoji: 🎬
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
---

# Wan Video Studio ZeroGPU Worker

Worker GPU para `Wan-Video-Studio` usando Wan 2.2 TI2V-5B y Hugging Face ZeroGPU.

## Configuración del Space

1. Crea un Space Gradio.
2. Copia el contenido de esta carpeta a la raíz del Space.
3. En Settings > Hardware selecciona ZeroGPU.
4. En Settings > Variables and secrets crea `WORKER_TOKEN` con un valor secreto.
5. Opcionalmente define:
   - `WAN_NUM_FRAMES=121`
   - `WAN_FPS=24`
   - `WAN_STEPS=20`

## API

El endpoint Gradio expuesto es `generate_video`.

Entradas:
- prompt
- aspect
- reference_image
- token

Salida:
- archivo MP4

121 frames a 24 FPS producen aproximadamente 5.04 segundos por escena.
