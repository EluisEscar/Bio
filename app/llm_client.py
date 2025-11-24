"""Cliente mínimo para interactuar con Ollama y obtener ayuda bioinformática."""

import os
from typing import Optional, Callable
import json

import requests

# Modelo preferido para las consultas; configurable con BIO_HELP_MODEL.
DEFAULT_MODEL = os.environ.get("BIO_HELP_MODEL", "phi3.5:3.8b")
# Dirección del servidor Ollama local/remoto.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Prompt del sistema que guía el tono y nivel de detalle de las respuestas.
SYSTEM_PROMPT = (
    "Actúas como un tutor de bioinformática de nivel básico para estudiantes universitarios. "
    "Respondes siempre en español, de forma directa y muy breve. "
    "Contesta únicamente a la pregunta concreta del usuario; no des introducciones generales "
    "ni expliques otros temas relacionados a menos que el usuario lo pida explícitamente. "
    "Si la pregunta es '¿qué es X?', responde con una definición clara en 1 frase, sin ejemplos ni listas, "
    "salvo que el usuario pida un ejemplo. "
    "Máximo 3 frases por respuesta. No uses viñetas ni numeraciones. "
    "Si el mensaje es solo un saludo, responde con un saludo corto y pide una duda específica de bioinformática. "
    "Si no estás seguro de algo, dilo claramente y sugiere verificarlo en una fuente confiable."
)


def _build_url(host: str, path: str) -> str:
    """Ensambla una URL limpia uniendo host y path sin dobles diagonales."""
    base = host.rstrip("/")
    suffix = path.lstrip("/")
    return f"{base}/{suffix}"


def generate_bio_help(
    question: str,
    *,
    model: Optional[str] = None,
    host: Optional[str] = None,
    timeout: float = 120.0,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str:
    """Realiza una pregunta al modelo local usando streaming y devuelve la respuesta completa."""
    q = (question or "").strip()
    if not q:
        raise ValueError("La pregunta no puede estar vacía.")

    model_name = model or DEFAULT_MODEL
    base = host or OLLAMA_HOST
    url = _build_url(base, "api/generate")
    payload = {
        "model": model_name,
        "prompt": q,
        "stream": True,
        "keep_alive": "10m",
        "system": SYSTEM_PROMPT,
        "options": {
            "num_ctx": 1024,
            "temperature": 0.5,
            "top_p": 0.7,
        },
    }

    try:
        # `stream=True` permite leer la salida del modelo por partes
        response = requests.post(url, json=payload, timeout=timeout, stream=True)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "No se pudo conectar con Ollama. ¿Está el servicio en ejecución en "
            f"{base}? Detalle: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama devolvió un error ({response.status_code}): {response.text}"
        )

    def _stream_chunks() -> str:
        partes: list[str] = []
        for line in response.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue

            chunk = (data.get("response") or "")
            if chunk:
                partes.append(chunk)
                if on_chunk:
                    on_chunk("".join(partes))

            if data.get("done"):
                break

        return ("".join(partes)).strip()

    text = _stream_chunks()
    if not text:
        raise RuntimeError("Ollama respondió, pero no se recibió texto.")
    return text
