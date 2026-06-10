"""Image generation dispatch.

Routes a prompt to the OpenAI or Gemini backend based on the model name.
Backends return (result, error): result is an http(s) URL or a local file
path to the image; on failure result is None and error is a short
human-readable reason suitable for the client error packet.
"""
import logging

from yail.config import ImageGenConfig
from yail.gen.gemini_backend import GEMINI_AVAILABLE, generate_image_with_gemini
from yail.gen.openai_backend import OPENAI_AVAILABLE, generate_image_with_openai
from yail.gen.util import short_error  # noqa: F401  (re-export)

logger = logging.getLogger(__name__)


def generate_image(prompt: str, gen_config: ImageGenConfig,
                   model: str | None = None) -> tuple[str | None, str | None]:
    """Generate an image; return (url_or_path, None) or (None, reason)."""
    model = model or gen_config.model

    logger.info(f"Generating image with model: {model}, prompt: '{prompt}'")

    if gen_config.is_gemini_model(model):
        return generate_image_with_gemini(prompt, gen_config, model=model)
    if gen_config.is_openai_model(model):
        return generate_image_with_openai(prompt, gen_config, model=model)

    logger.error(f"Unsupported model: {model}")
    return None, f"Unsupported model: {model}"
