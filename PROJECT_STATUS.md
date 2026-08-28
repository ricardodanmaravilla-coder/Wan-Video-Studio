# Estado del proyecto

## MVP 0.1

Implementado:
- FastAPI web app.
- Worker separado.
- Modo MOCK sin GPU.
- Generación de 5 a 30 segundos.
- División en escenas.
- Unión con FFmpeg.
- Formatos 16:9, 9:16 y 1:1.
- Adaptador inicial para Wan 2.2 TI2V-5B.
- Dockerfiles para web y worker.
- Docker Compose para prueba local.
- Cloud Build para frontend en Cloud Run.

## Fase 0.2
- Upload de imagen de referencia.
- Persistencia del último frame.
- Continuidad entre escenas.
- Progreso por escena.
- Cancelación/reintento.
- Almacenamiento compatible con worker remoto.

## Fase 0.3
- Storyboard con LLM.
- Audio, voz y subtítulos.
- Upscale.
- Galería de proyectos.
