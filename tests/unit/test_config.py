import json
from pathlib import Path
import pytest
from src.config.channel import ChannelConfig, SubtitleStyle, load_channel_config


def test_channel_config_loads_from_json(tmp_path):
    config_dir = tmp_path / "channels" / "test_ch"
    config_dir.mkdir(parents=True)
    config = {
        "channel_id": "test_ch",
        "youtube_channel_id": "UCtest",
        "voice_id": "voice_123",
        "concurrency": 4,
        "visual_style_presets": {"default": "dark cinematic"},
        "subtitle_style": {
            "font": "NanumGothicBold",
            "size": 52,
            "color": "white",
            "outline": 3,
            "position": "bottom_third",
        },
        "bgm_enabled": True,
        "bgm_volume": 0.15,
    }
    (config_dir / "config.json").write_text(json.dumps(config))

    ch = load_channel_config("test_ch", channels_dir=tmp_path / "channels")

    assert ch.channel_id == "test_ch"
    assert ch.voice_id == "voice_123"
    assert ch.concurrency == 4
    assert ch.subtitle_style.font == "NanumGothicBold"
    assert ch.bgm_volume == 0.15


def test_channel_config_defaults():
    ch = ChannelConfig(channel_id="x", voice_id="v")
    assert ch.concurrency == 3
    assert ch.bgm_enabled is True
    assert ch.bgm_volume == 0.15
    assert isinstance(ch.subtitle_style, SubtitleStyle)


from src.config.settings import Settings


def _base_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setenv("FLUX_API_KEY", "flux-test")
    monkeypatch.setenv("KLING_API_KEY", "kling-test")
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt-test")


def test_settings_loads_from_env(monkeypatch):
    _base_env(monkeypatch)
    settings = Settings()
    assert settings.anthropic_api_key == "sk-test"
    assert settings.max_retries == 3
    assert settings.default_concurrency == 3


def test_settings_override_defaults(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("MAX_RETRIES", "5")
    monkeypatch.setenv("DEFAULT_CONCURRENCY", "2")
    settings = Settings()
    assert settings.max_retries == 5
    assert settings.default_concurrency == 2
