"""Image generation dispatch.

Routes a prompt to the OpenAI or Gemini backend based on the model name.
Backends return either an http(s) URL or a local file path to the image,
or None on failure.
"""
import logging

from yail.config import ImageGenConfig
from yail.gen.gemini_backend import GEMINI_AVAILABLE, generate_image_with_gemini
from yail.gen.openai_backend import OPENAI_AVAILABLE, generate_image_with_openai

logger = logging.getLogger(__name__)


def generate_image(prompt: str, gen_config: ImageGenConfig, model: str | None = None) -> str | None:
    """Generate an image and return its URL or local path, or None on failure."""
    model = model or gen_config.model

    logger.info(f"Generating image with model: {model}, prompt: '{prompt}'")

    if gen_config.is_gemini_model(model):
        return generate_image_with_gemini(prompt, gen_config, model=model)
    if gen_config.is_openai_model(model):
        return generate_image_with_openai(prompt, gen_config, model=model)

    logger.error(f"Unsupported model: {model}")
    return None
