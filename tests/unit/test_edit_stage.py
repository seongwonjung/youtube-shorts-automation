import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.stages.edit import EditStage
from src.pipeline.context import (
    PipelineContext, TTSResult, SceneTTS, ImageVideoResult, SceneMedia,
)
from src.config.channel import ChannelConfig
from src.config.settings import Settings


def _make_settings():
    return Settings(
        anthropic_api_key="x",
        elevenlabs_api_key="x",
        youtube_api_key="x",
        flux_api_key="fal-key",
        kling_api_key="fal-key",
    )


def _make_ctx(tmp_path):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(
        run_id="r1", run_dir=tmp_path, channel_name="test",
        channel=channel, urls=[], topic="test",
    )
    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    (tts_dir / "scene_1.mp3").write_bytes(b"audio")
    (tts_dir / "scene_1.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello", encoding="utf-8")

    iv_dir = tmp_path / "image_video"
    iv_dir.mkdir()
    (iv_dir / "scene_1.mp4").write_bytes(b"video")

    ctx.tts = TTSResult(
        scenes=[SceneTTS(scene_no=1, audio_path="tts/scene_1.mp3", srt_path="tts/scene_1.srt")],
        voice_id="v1",
    )
    ctx.image_video = ImageVideoResult(
        scenes=[SceneMedia(scene_no=1, image_path="image_video/scene_1.png", video_path="image_video/scene_1.mp4")],
    )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_edit(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = EditStage(settings=_make_settings())

    with patch("src.stages.edit.ffmpeg_svc.mux_video_audio", new_callable=AsyncMock) as mock_mux, \
         patch("src.stages.edit.ffmpeg_svc.concat_videos", new_callable=AsyncMock) as mock_concat, \
         patch("src.stages.edit.ffmpeg_svc.burn_subtitles", new_callable=AsyncMock) as mock_burn:

        async def fake_mux(v, a, o): o.write_bytes(b"muxed")
        async def fake_concat(clips, out): out.write_bytes(b"concat")
        async def fake_burn(v, s, o): o.write_bytes(b"final")
        mock_mux.side_effect = fake_mux
        mock_concat.side_effect = fake_concat
        mock_burn.side_effect = fake_burn

        result = await stage.run(ctx)

    assert result.edit is not None
    assert result.edit.video_path == "final_shorts.mp4"


@pytest.mark.asyncio
async def test_raises_if_no_tts(tmp_path):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(run_id="r1", run_dir=tmp_path, channel_name="test",
                         channel=channel, urls=[], topic="test")
    ctx.image_video = ImageVideoResult(scenes=[])
    stage = EditStage(settings=_make_settings())
    with pytest.raises(ValueError, match="tts"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_raises_if_no_image_video(tmp_path):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(run_id="r1", run_dir=tmp_path, channel_name="test",
                         channel=channel, urls=[], topic="test")
    ctx.tts = TTSResult(scenes=[])
    stage = EditStage(settings=_make_settings())
    with pytest.raises(ValueError, match="image_video"):
        await stage.run(ctx)
