"""OpenAI image generation: gpt-image-1 and DALL-E 2/3."""
import base64
import logging
import os
import time
import traceback

from yail.config import ImageGenConfig
from yail.gen.util import short_error

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


def _rejected_param(e: Exception) -> str | None:
    """Return the parameter name from an 'unknown_parameter' API error."""
    body = getattr(e, "body", None) or {}
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict) and err.get("code") == "unknown_parameter":
            return err.get("param")
    return None


def generate_image_with_openai(prompt: str, gen_config: ImageGenConfig,
                               model: str | None = None) -> tuple[str | None, str | None]:
    """Generate an image with OpenAI; return (url_or_path, None) or (None, reason)."""
    if not OPENAI_AVAILABLE:
        logger.error("OpenAI library not available. Install with: pip install openai")
        return None, "OpenAI library not installed on server"

    api_key = gen_config.api_key
    model = model or gen_config.model
    size = gen_config.size

    if not api_key:
        logger.error("OpenAI API key not provided. Set OPENAI_API_KEY.")
        return None, "OpenAI API key not configured on server"

    try:
        logger.info(f"Generating image with OpenAI model: {model}, prompt: '{prompt}'")
        client = openai.OpenAI(api_key=api_key)

        kwargs: dict = {"model": model, "prompt": prompt, "n": 1}
        if model.lower().startswith("gpt-image"):
            # gpt-image-1 returns base64 only and uses its own quality values.
            quality = gen_config.quality
            if quality not in gen_config.VALID_QUALITIES["gpt-image-1"]:
                quality = "auto"
            if size not in gen_config.VALID_SIZES["gpt-image-1"]:
                size = "auto"
            kwargs.update(size=size, quality=quality)
        elif model.lower() == "dall-e-3":
            kwargs.update(size=size, quality=gen_config.quality,
                          style=gen_config.style)
        else:
            # DALL-E 2 (and unknown gpt-* fallbacks): size only.
            kwargs.update(size=size)

        # The Images API drops legacy parameters over time (response_format
        # and style are already gone) and rejects them with 400
        # unknown_parameter. Retry without any parameter it refuses.
        while True:
            try:
                response = client.images.generate(**kwargs)
                break
            except openai.BadRequestError as e:
                param = _rejected_param(e)
                if param and param in kwargs and param not in ("model", "prompt"):
                    logger.warning(f"OpenAI rejected parameter '{param}'; "
                                   f"retrying without it")
                    kwargs.pop(param)
                    continue
                raise

        item = response.data[0]
        if getattr(item, "url", None):
            logger.info(f"Image generated successfully with OpenAI: {item.url}")
            return item.url, None
        if getattr(item, "b64_json", None):
            path = _save_b64_image(item.b64_json, "openai")
            logger.info(f"Image generated successfully with OpenAI: {path}")
            return path, None
        logger.error("OpenAI response contained neither a URL nor image data")
        return None, "OpenAI returned no image data"

    except Exception as e:
        logger.error(f"Error generating image with OpenAI: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None, short_error(e)
