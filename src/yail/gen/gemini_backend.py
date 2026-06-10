"""Google Gemini image generation via the google-genai SDK."""
import logging
import os
import time
import traceback

from yail.config import ImageGenConfig
from yail.gen.util import short_error

logger = logging.getLogger(__name__)

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai library not available. Install with: pip install google-genai")

GENERATED_DIR = "generated_images"


def generate_image_with_gemini(prompt: str, gen_config: ImageGenConfig,
                               model: str | None = None) -> tuple[str | None, str | None]:
    """Generate an image with Gemini; return (file_path, None) or (None, reason)."""
    if not GEMINI_AVAILABLE:
        logger.error("google-genai library not available. Install with: pip install google-genai")
        return None, "Gemini library not installed on server"

    api_key = gen_config.gemini_api_key
    if not api_key:
        logger.error("Gemini API key not provided. Set GEMINI_API_KEY.")
        return None, "Gemini API key not configured on server"

    model = model or gen_config.model
    if not gen_config.is_gemini_model(model):
        model = gen_config.DEFAULT_GEMINI_MODEL

    try:
        logger.info(f"Generating image with Gemini model: {model}, prompt: '{prompt}'")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)

        if not response.candidates:
            logger.error("No candidates in Gemini response")
            return None, "Gemini returned no candidates"

        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                os.makedirs(GENERATED_DIR, exist_ok=True)
                path = os.path.join(GENERATED_DIR, f"gemini-{int(time.time())}.png")
                # inline_data.data is raw bytes in the google-genai SDK.
                with open(path, "wb") as f:
                    f.write(part.inline_data.data)
                abs_path = os.path.abspath(path)
                logger.info(f"Image generated successfully with Gemini: {abs_path}")
                return abs_path, None
            if getattr(part, "text", None):
                logger.info(f"Gemini text response: {part.text}")

        logger.error("Failed to extract image from Gemini response")
        return None, "Gemini response contained no image"

    except Exception as e:
        logger.error(f"Error generating image with Gemini: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None, short_error(e)
