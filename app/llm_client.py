"""Cliente mínimo para interactuar con Ollama y obtener ayuda bioinformática."""

import os
from typing import Optional
import json

import requests

# Modelo preferido para las consultas; configurable con BIO_HELP_MODEL.
DEFAULT_MODEL = os.environ.get("BIO_HELP_MODEL", "phi3.5:3.8b")
# Dirección del servidor Ollama local/remoto.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Prompt del sistema que guía el tono y nivel de detalle de las respuestas.
SYSTEM_PROMPT = (
    "Eres un tutor de bioinformática de nivel básico. Responde en español y con tono didáctico, "
    "Ofreciendo definiciones breves, ejemplos simples y pasos accionables cuando sea posible. "
    "Sé conciso y evita derivaciones innecesarias o alucionaciones que no tengan que ver con el tema."
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
        "system": SYSTEM_PROMPT,
        "options": {
            "num_predict": 256,
            "temperature": 0.6,
            "top_p": 0.9,
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

    partes: list[str] = []

    # Cada línea del stream es un JSON con un fragmento de la respuesta
    for line in response.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            # Si llega alguna línea rara, se ignora
            continue

        chunk = (data.get("response") or "")
        if chunk:
            partes.append(chunk)

        # Cuando Ollama indica que terminó, salimos del bucle
        if data.get("done"):
            break

    text = ("".join(partes)).strip()
    if not text:
        raise RuntimeError("Ollama respondió, pero no se recibió texto.")
    return text
