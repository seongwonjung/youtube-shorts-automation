import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.stages.image_video import ImageVideoStage
from src.pipeline.context import (
    PipelineContext, StoryboardResult, EnhancedScene, ImageVideoResult,
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


def _make_ctx(tmp_path, with_storyboard=True):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(
        run_id="r1", run_dir=tmp_path, channel_name="test",
        channel=channel, urls=[], topic="test",
    )
    if with_storyboard:
        ctx.storyboard = StoryboardResult(
            scenes=[
                EnhancedScene(scene_no=1, enhanced_prompt="forest", negative_prompt="blur"),
                EnhancedScene(scene_no=2, enhanced_prompt="city", negative_prompt="dark"),
            ],
            visual_style="cinematic",
        )
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_image_video(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = ImageVideoStage(settings=_make_settings())

    with patch("src.stages.image_video.FluxService") as MockFlux, \
         patch("src.stages.image_video.KlingService") as MockKling:
        flux_inst = MockFlux.return_value
        kling_inst = MockKling.return_value
        flux_inst.generate_image = AsyncMock(side_effect=[
            "image_video/scene_1.png",
            "image_video/scene_2.png",
        ])
        kling_inst.generate_video = AsyncMock(side_effect=[
            "image_video/scene_1.mp4",
            "image_video/scene_2.mp4",
        ])

        result = await stage.run(ctx)

    assert result.image_video is not None
    assert len(result.image_video.scenes) == 2
    assert result.image_video.scenes[0].scene_no == 1


@pytest.mark.asyncio
async def test_raises_if_no_storyboard(tmp_path):
    ctx = _make_ctx(tmp_path, with_storyboard=False)
    stage = ImageVideoStage(settings=_make_settings())
    with pytest.raises(ValueError, match="storyboard"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_skips_existing_image_file(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = ImageVideoStage(settings=_make_settings())

    iv_dir = tmp_path / "image_video"
    iv_dir.mkdir()
    (iv_dir / "scene_1.png").write_bytes(b"fake")
    (iv_dir / "scene_1.mp4").write_bytes(b"fake")

    with patch("src.stages.image_video.FluxService") as MockFlux, \
         patch("src.stages.image_video.KlingService") as MockKling:
        flux_inst = MockFlux.return_value
        kling_inst = MockKling.return_value
        flux_inst.generate_image = AsyncMock(return_value="image_video/scene_2.png")
        kling_inst.generate_video = AsyncMock(return_value="image_video/scene_2.mp4")

        result = await stage.run(ctx)

    flux_inst.generate_image.assert_called_once()
    assert result.image_video is not None
