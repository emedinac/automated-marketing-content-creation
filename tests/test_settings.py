import pytest

from marketing_collateral.settings import Settings


def test_settings_loads_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Settings gives real environment variables precedence over .env.
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    settings = Settings()

    assert settings.google_cloud_project == "test-project"
    assert settings.google_cloud_location == "europe-west4"
    assert settings.gemini_model == "test-model"
