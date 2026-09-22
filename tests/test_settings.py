from investment_research.settings import Settings, settings


def test_settings_have_operational_defaults() -> None:
    assert settings.app_name
    assert settings.model_name
    assert settings.stock_price_max_tokens > 0
    assert settings.default_ticker
    assert settings.log_level
    assert settings.log_file


def test_settings_are_immutable() -> None:
    configured = Settings()
    try:
        configured.model_name = "another-model"
    except AttributeError:
        pass
    else:
        raise AssertionError("Settings should be immutable")