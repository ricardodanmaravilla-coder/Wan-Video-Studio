# Wan Video Studio

Aplicación propia para generar videos largos a partir de escenas cortas.

## Arquitectura

- `app/`: interfaz web + API FastAPI.
- `worker/`: motor de generación. Arranca en modo MOCK para probar todo sin GPU.
- El frontend pide un video de 5, 10, 15, 20, 25 o 30 segundos.
- El backend divide el trabajo en escenas de ~5 s.
- El worker genera cada escena.
- FFmpeg une las escenas y crea el MP4 final.

## 1. Prueba inmediata sin GPU

Requisitos:
- Python 3.11+
- FFmpeg instalado

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:MOCK_MODE="1"
python -m uvicorn worker.app:app --host 127.0.0.1 --port 7860
```

Abre otra PowerShell:

```powershell
.venv\Scripts\Activate.ps1
$env:WORKER_URL="http://127.0.0.1:7860"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Abre `http://127.0.0.1:8080`.

El modo MOCK crea clips de prueba con FFmpeg para validar la aplicación completa.

## 2. Modo Wan real

El archivo `worker/wan_engine.py` deja preparado un adaptador para Wan 2.2 TI2V-5B.

Variables:

```text
MOCK_MODE=0
WAN_REPO=/ruta/Wan2.2
WAN_CKPT=/ruta/Wan2.2-TI2V-5B
WAN_SIZE=1280*704
```

## 3. Videos de 30 segundos

La aplicación no intenta generar 30 s de una sola vez.

`30 s = 6 escenas x ~5 s`

Esto permite reintentar solo una escena fallida, usar GPUs con cuota y mantener el motor intercambiable.

## Docker Compose

```bash
docker compose up --build
```

Luego abre `http://localhost:8080`.

Esto ejecuta la interfaz y un worker MOCK. No descarga Wan ni necesita GPU.
