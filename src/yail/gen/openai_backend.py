"""OpenAI image generation: gpt-image-1 and DALL-E 2/3."""
import base64
import logging
import os
import time
import traceback

from yail.config import ImageGenConfig

logger = logging.getLogger(__name__)

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not available. Install with: pip install openai")

GENERATED_DIR = "generated_images"


def _save_b64_image(b64_data: str, prefix: str) -> str:
    os.makedirs(GENERATED_DIR, exist_ok=True)
    path = os.path.join(GENERATED_DIR, f"{prefix}-{int(time.time())}.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return os.path.abspath(path)


def generate_image_with_openai(prompt: str, gen_config: ImageGenConfig,
                               model: str | None = None) -> str | None:
    """Generate an image with OpenAI; return a URL (DALL-E) or file path (gpt-image-1)."""
    if not OPENAI_AVAILABLE:
        logger.error("OpenAI library not available. Install with: pip install openai")
        return None

    api_key = gen_config.api_key
    model = model or gen_config.model
    size = gen_config.size

    if not api_key:
        logger.error("OpenAI API key not provided. Set OPENAI_API_KEY.")
        return None

    try:
        logger.info(f"Generating image with OpenAI model: {model}, prompt: '{prompt}'")
        client = openai.OpenAI(api_key=api_key)

        if model.lower().startswith("gpt-image"):
            # gpt-image-1 returns base64 only and uses its own quality values.
            quality = gen_config.quality
            if quality not in gen_config.VALID_QUALITIES["gpt-image-1"]:
                quality = "auto"
            if size not in gen_config.VALID_SIZES["gpt-image-1"]:
                size = "auto"
            response = client.images.generate(
                model=model, prompt=prompt, size=size, quality=quality, n=1,
            )
            path = _save_b64_image(response.data[0].b64_json, "openai")
            logger.info(f"Image generated successfully with OpenAI: {path}")
            return path

        if model.lower() == "dall-e-3":
            response = client.images.generate(
                model=model, prompt=prompt, size=size,
                quality=gen_config.quality, style=gen_config.style,
                n=1, response_format="url",
            )
        else:
            # DALL-E 2 (and unknown gpt-* fallbacks): no quality/style params.
            response = client.images.generate(
                model=model, prompt=prompt, size=size, n=1, response_format="url",
            )

        image_url = response.data[0].url
        logger.info(f"Image generated successfully with OpenAI: {image_url}")
        return image_url

    except Exception as e:
        logger.error(f"Error generating image with OpenAI: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None
