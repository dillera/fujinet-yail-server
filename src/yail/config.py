"""Configuration for the YAIL server and its image-generation backends.

Settings precedence (lowest to highest): process environment, env file
(server/env or .env via python-dotenv), command-line arguments.
"""
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_PORT = 5556
DEFAULT_EXTENSIONS = [".jpg", ".jpeg", ".gif", ".png"]


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    paths: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=lambda: list(DEFAULT_EXTENSIONS))
    camera: str | None = None
    enable_camera: bool = False
    # Local file serving is opt-in: the 'files' command only works when this
    # is true AND an explicit folder path was configured (CLI, env, or UI).
    files_enabled: bool = False
    # Streaming: the client slideshow loop driven by the 'next' command.
    streaming_enabled: bool = True
    stream_max_retries: int = 10     # attempts before giving up on a source list
    stream_retry_wait: float = 1.0   # seconds between retries on a bad image
    download_timeout: float = 5.0    # seconds to fetch a remote image
    # Image search: ordered DDGS engine names, or ["auto"] for all engines.
    search_backends: list[str] = field(default_factory=lambda: ["auto"])
    search_max_results: int = 1000


def valid_search_backends() -> list[str]:
    """Image search engines available in the installed ddgs package."""
    try:
        from ddgs.engines import ENGINES
        engines = sorted(set(ENGINES.get("images", [])))
    except Exception:
        engines = ["bing", "duckduckgo"]
    return ["auto"] + engines


class ImageGenConfig:
    """Validated settings for the image-generation backends."""

    OPENAI_MODEL_PREFIXES = ["dall-e-", "gpt-"]
    GEMINI_MODEL_PREFIXES = ["gemini"]

    # dall-e-* models were retired from the OpenAI Images API in 2025/2026;
    # gpt-image-1 is the current generation model.
    DEFAULT_MODEL = "gpt-image-1"
    DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-image"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_QUALITY = "auto"   # gpt-image-1 quality; dall-e used "standard"
    DEFAULT_STYLE = "vivid"

    # Per model family.  "style" only applies to dall-e-3.
    VALID_SIZES = {
        "dall-e-3": ["1024x1024", "1792x1024", "1024x1792"],
        "dall-e-2": ["256x256", "512x512", "1024x1024"],
        "gpt-image-1": ["1024x1024", "1536x1024", "1024x1536", "auto"],
    }
    VALID_QUALITIES = {
        "dall-e-3": ["standard", "hd"],
        "dall-e-2": ["standard"],
        "gpt-image-1": ["low", "medium", "high", "auto"],
    }
    VALID_STYLES = ["vivid", "natural"]

    def __init__(self) -> None:
        self.model = os.environ.get("GEN_MODEL", os.environ.get("OPENAI_MODEL", self.DEFAULT_MODEL))

        # A bare "gemini" means "the default Gemini image model".
        if self.model.lower() == "gemini":
            self.model = self.DEFAULT_GEMINI_MODEL
            logger.info(f"Generic 'gemini' resolved to: {self.model}")

        self.size = os.environ.get("OPENAI_SIZE", self.DEFAULT_SIZE)
        self.quality = os.environ.get("OPENAI_QUALITY", self.DEFAULT_QUALITY)
        self.style = os.environ.get("OPENAI_STYLE", self.DEFAULT_STYLE)
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.system_prompt = os.environ.get(
            "OPENAI_SYSTEM_PROMPT",
            "You are an image generation assistant. Generate an image based on the user's description.",
        )

        logger.info(f"ImageGenConfig initialized with model: {self.model}")
        logger.info(f"OPENAI_API_KEY: {'set' if self.api_key else 'not set'}, "
                    f"GEMINI_API_KEY: {'set' if self.gemini_api_key else 'not set'}")

        if not self.is_valid_model(self.model):
            logger.warning(f"Unknown model format: {self.model}. Using default: {self.DEFAULT_MODEL}")
            self.model = self.DEFAULT_MODEL
        if not self._size_valid(self.size):
            logger.warning(f"Invalid OPENAI_SIZE: {self.size}. Using default: {self.DEFAULT_SIZE}")
            self.size = self.DEFAULT_SIZE
        if not self._quality_valid(self.quality):
            logger.warning(f"Invalid OPENAI_QUALITY: {self.quality}. Using default: {self.DEFAULT_QUALITY}")
            self.quality = self.DEFAULT_QUALITY
        if self.style not in self.VALID_STYLES:
            logger.warning(f"Invalid OPENAI_STYLE: {self.style}. Using default: {self.DEFAULT_STYLE}")
            self.style = self.DEFAULT_STYLE

    def _model_family(self, model: str | None = None) -> str:
        model = (model or self.model).lower()
        for family in self.VALID_SIZES:
            if model.startswith(family):
                return family
        return "dall-e-3"

    def _size_valid(self, size: str) -> bool:
        return size in self.VALID_SIZES[self._model_family()]

    def _quality_valid(self, quality: str) -> bool:
        return quality in self.VALID_QUALITIES[self._model_family()]

    def is_valid_model(self, model: str) -> bool:
        if not model:
            return False
        prefixes = self.OPENAI_MODEL_PREFIXES + self.GEMINI_MODEL_PREFIXES
        return any(model.lower().startswith(p.lower()) for p in prefixes)

    def is_openai_model(self, model: str | None = None) -> bool:
        model = model or self.model
        return any(model.lower().startswith(p.lower()) for p in self.OPENAI_MODEL_PREFIXES)

    def is_gemini_model(self, model: str | None = None) -> bool:
        model = model or self.model
        return "gemini" in model.lower()

    def set_model(self, model: str) -> bool:
        if model and model.lower() == "gemini":
            model = self.DEFAULT_GEMINI_MODEL
        if self.is_valid_model(model):
            self.model = model
            logger.info(f"Model set to: {model}")
            return True
        logger.warning(f"Invalid model: {model}. Model must start with one of: "
                       f"{', '.join(self.OPENAI_MODEL_PREFIXES + self.GEMINI_MODEL_PREFIXES)}")
        return False

    def set_size(self, size: str) -> bool:
        if self._size_valid(size):
            self.size = size
            logger.info(f"Size set to: {size}")
            return True
        logger.warning(f"Invalid size: {size}. Valid options for {self._model_family()}: "
                       f"{', '.join(self.VALID_SIZES[self._model_family()])}")
        return False

    def set_quality(self, quality: str) -> bool:
        if self._quality_valid(quality):
            self.quality = quality
            logger.info(f"Quality set to: {quality}")
            return True
        logger.warning(f"Invalid quality: {quality}. Valid options for {self._model_family()}: "
                       f"{', '.join(self.VALID_QUALITIES[self._model_family()])}")
        return False

    def set_style(self, style: str) -> bool:
        if style in self.VALID_STYLES:
            self.style = style
            logger.info(f"Style set to: {style}")
            return True
        logger.warning(f"Invalid style: {style}. Valid options are: {', '.join(self.VALID_STYLES)}")
        return False

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key
        logger.info("API key updated")

    def set_system_prompt(self, system_prompt: str) -> bool:
        self.system_prompt = system_prompt
        logger.info(f"System prompt updated: {system_prompt}")
        return True

    def __str__(self) -> str:
        return (f"ImageGenConfig(model={self.model}, size={self.size}, "
                f"quality={self.quality}, style={self.style})")
