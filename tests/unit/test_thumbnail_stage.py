import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.stages.thumbnail import ThumbnailStage
from src.pipeline.context import PipelineContext, ScriptResult, YouTubeMeta
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


def _make_ctx(tmp_path, with_script=True):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(
        run_id="r1", run_dir=tmp_path, channel_name="test",
        channel=channel, urls=[], topic="test-topic",
    )
    if with_script:
        ctx.script = ScriptResult(
            title="테스트 제목",
            thumbnail_prompt="epic cinematic thumbnail",
            youtube_meta=YouTubeMeta(title="테스트 제목"),
        )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_thumbnail(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = ThumbnailStage(settings=_make_settings())

    with patch("src.stages.thumbnail.FluxService") as MockFlux:
        flux_inst = MockFlux.return_value
        flux_inst.generate_thumbnail = AsyncMock(return_value="thumbnail.png")

        result = await stage.run(ctx)

    assert result.thumbnail is not None
    assert result.thumbnail.image_path == "thumbnail.png"
    assert "thumbnail" in result.completed_stages


@pytest.mark.asyncio
async def test_raises_if_no_script(tmp_path):
    ctx = _make_ctx(tmp_path, with_script=False)
    stage = ThumbnailStage(settings=_make_settings())
    with pytest.raises(ValueError, match="script"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_uses_topic_when_no_thumbnail_prompt(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.script.thumbnail_prompt = ""
    ctx.script.title = ""
    stage = ThumbnailStage(settings=_make_settings())

    with patch("src.stages.thumbnail.FluxService") as MockFlux:
        flux_inst = MockFlux.return_value
        flux_inst.generate_thumbnail = AsyncMock(return_value="thumbnail.png")

        await stage.run(ctx)

    call_kwargs = flux_inst.generate_thumbnail.call_args
    assert call_kwargs.kwargs["prompt"] == "test-topic"


@pytest.mark.asyncio
async def test_uses_channel_thumbnail_ratio(tmp_path):
    ctx = _make_ctx(tmp_path)
    ctx.channel.thumbnail_ratio = "portrait_9_16"
    stage = ThumbnailStage(settings=_make_settings())

    with patch("src.stages.thumbnail.FluxService") as MockFlux:
        flux_inst = MockFlux.return_value
        flux_inst.generate_thumbnail = AsyncMock(return_value="thumbnail.png")

        await stage.run(ctx)

    call_kwargs = flux_inst.generate_thumbnail.call_args
    assert call_kwargs.kwargs["image_size"] == "portrait_9_16"


@pytest.mark.asyncio
async def test_default_thumbnail_ratio_is_landscape(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = ThumbnailStage(settings=_make_settings())

    with patch("src.stages.thumbnail.FluxService") as MockFlux:
        flux_inst = MockFlux.return_value
        flux_inst.generate_thumbnail = AsyncMock(return_value="thumbnail.png")

        await stage.run(ctx)

    call_kwargs = flux_inst.generate_thumbnail.call_args
    assert call_kwargs.kwargs["image_size"] == "landscape_16_9"
