# Deploy automático a Hugging Face Spaces

Wan Video Studio incluye un GitHub Action que publica automáticamente los workers en estos Spaces:

- `wan-video-studio-t2v`
- `wan-video-studio-i2v`

## 1. Crear un token de Hugging Face

En Hugging Face crea un User Access Token con permiso de escritura sobre tus repositorios/Spaces.

No pegues ese token en el código ni en `.env`.

## 2. Guardarlo en GitHub

En el repositorio `Wan-Video-Studio` abre:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Nombre exacto:

`HF_TOKEN`

Valor: tu token de Hugging Face.

## 3. Ejecutar el despliegue

Abre:

`Actions -> Deploy Hugging Face Spaces -> Run workflow`

En `hf_username` escribe tu usuario exacto de Hugging Face.

El workflow clonará los dos Spaces, copiará automáticamente:

- `hf_spaces/t2v/*` al Space T2V
- `hf_spaces/i2v/*` al Space I2V

y hará push a Hugging Face.

## 4. Secretos de los Spaces

En cada Space, abre `Settings -> Variables and secrets` y añade el mismo secreto:

`WORKER_TOKEN`

Usa un valor largo y aleatorio. Ese mismo valor debe configurarse después en Cloud Run.

## 5. Variables para la aplicación principal

Cloud Run deberá ejecutar con:

```text
WORKER_MODE=gradio
HF_SPACE_T2V=<usuario>/wan-video-studio-t2v
HF_SPACE_I2V=<usuario>/wan-video-studio-i2v
WORKER_TOKEN=<mismo secreto de los Spaces>
HF_TOKEN=<token opcional si los Spaces son privados>
```

Si los Spaces son públicos, `HF_TOKEN` puede quedar vacío para llamadas normales; ZeroGPU puede aplicar su propia autenticación/cuota al llamador.

## Seguridad

Nunca guardes `HF_TOKEN` ni `WORKER_TOKEN` en un archivo público, commit, README o variable visible. Usa secretos de GitHub, Hugging Face y Cloud Run/Secret Manager.
