"""ImageGenConfig validation and environment handling tests."""
import pytest

from yail.config import ImageGenConfig


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("GEN_MODEL", "OPENAI_MODEL", "OPENAI_SIZE", "OPENAI_QUALITY",
                "OPENAI_STYLE", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_defaults():
    cfg = ImageGenConfig()
    assert cfg.model == "dall-e-3"
    assert cfg.size == "1024x1024"
    assert cfg.quality == "standard"
    assert cfg.style == "vivid"


def test_env_model(monkeypatch):
    monkeypatch.setenv("GEN_MODEL", "gpt-image-1")
    assert ImageGenConfig().model == "gpt-image-1"


def test_bare_gemini_resolves_to_default_image_model(monkeypatch):
    monkeypatch.setenv("GEN_MODEL", "gemini")
    cfg = ImageGenConfig()
    assert cfg.model == ImageGenConfig.DEFAULT_GEMINI_MODEL
    assert cfg.is_gemini_model()


def test_invalid_model_falls_back(monkeypatch):
    monkeypatch.setenv("GEN_MODEL", "stable-diffusion-9000")
    assert ImageGenConfig().model == "dall-e-3"


def test_model_routing():
    cfg = ImageGenConfig()
    assert cfg.is_openai_model("dall-e-2")
    assert cfg.is_openai_model("gpt-image-1")
    assert cfg.is_gemini_model("gemini-2.5-flash-image")
    assert not cfg.is_gemini_model("dall-e-3")


def test_set_size_validates_per_model():
    cfg = ImageGenConfig()
    assert cfg.set_size("1792x1024")           # valid for dall-e-3
    assert not cfg.set_size("1536x1024")       # gpt-image-1 size, invalid for dall-e-3
    assert cfg.set_model("gpt-image-1")
    assert cfg.set_size("1536x1024")


def test_set_quality_validates_per_model():
    cfg = ImageGenConfig()
    assert cfg.set_quality("hd")
    assert not cfg.set_quality("high")
    cfg.set_model("gpt-image-1")
    assert cfg.set_quality("high")


def test_set_system_prompt_returns_true():
    # The legacy implementation returned None, which made the server report
    # an error to the client even when the prompt was set successfully.
    cfg = ImageGenConfig()
    assert cfg.set_system_prompt("draw like it's 1979") is True
    assert cfg.system_prompt == "draw like it's 1979"
