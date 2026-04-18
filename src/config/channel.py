from pathlib import Path
from pydantic import BaseModel


class SubtitleStyle(BaseModel):
    font: str = "NanumGothicBold"
    size: int = 52
    color: str = "white"
    outline: int = 3
    position: str = "bottom_third"


class ChannelConfig(BaseModel):
    channel_id: str
    youtube_channel_id: str = ""
    voice_id: str
    concurrency: int = 3
    visual_style_presets: dict[str, str] = {}
    subtitle_style: SubtitleStyle = SubtitleStyle()
    bgm_enabled: bool = True
    bgm_volume: float = 0.15
    thumbnail_ratio: str = "landscape_16_9"  # A: landscape_16_9 | B: portrait_9_16


def load_channel_config(
    channel_name: str,
    channels_dir: Path = Path("channels"),
) -> ChannelConfig:
    path = channels_dir / channel_name / "config.json"
    return ChannelConfig.model_validate_json(path.read_text(encoding="utf-8"))
