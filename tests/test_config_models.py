"""Tests for config model list."""

from content_judge.config import AVAILABLE_MODELS


def test_available_models_is_list():
    assert isinstance(AVAILABLE_MODELS, list)
    assert len(AVAILABLE_MODELS) >= 2


def test_default_model_is_first():
    """The default model should be the first in the list."""
    from content_judge.config import Settings
    settings_default = Settings.__fields__["default_model"].default
    assert AVAILABLE_MODELS[0] == settings_default
