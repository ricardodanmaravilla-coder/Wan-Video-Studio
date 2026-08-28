# Deploy en Streamlit Community Cloud

## App

- Repositorio: `ricardodanmaravilla-coder/Wan-Video-Studio`
- Rama: `main`
- Main file path: `streamlit_app.py`
- Python recomendado: 3.11

## Secrets

En **App settings -> Secrets** pega:

```toml
WORKER_TOKEN = "PEGA_AQUI_EL_MISMO_WORKER_TOKEN_DE_HUGGING_FACE"
HF_SPACE_T2V = "RicasMaravilla/wan-video-studio-t2v"
HF_SPACE_I2V = "RicasMaravilla/wan-video-studio-i2v"
```

`HF_TOKEN` no es necesario si los Spaces son públicos. Si más adelante se vuelven privados, agrega:

```toml
HF_TOKEN = "hf_xxx"
```

Nunca subas `.streamlit/secrets.toml` al repositorio.

## ZeroGPU

Los dos Spaces deben tener el mismo secreto `WORKER_TOKEN`. El workflow `.github/workflows/deploy-hf-spaces.yml` puede sincronizarlo automáticamente desde el secret `WORKER_TOKEN` de GitHub Actions.

## Dependencias

- Python: `requirements.txt`
- Sistema: `packages.txt` instala FFmpeg

## Primera prueba

Empieza con un video de 5 segundos en 16:9. Después prueba 10 segundos para verificar continuidad T2V -> I2V. Los videos de 30 segundos requieren seis llamadas y pueden superar la cuota gratuita de ZeroGPU.
