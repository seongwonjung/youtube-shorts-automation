import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.stages.upload import UploadStage
from src.pipeline.context import (
    PipelineContext, EditResult, ThumbnailResult, ScriptResult, YouTubeMeta,
)
from src.config.channel import ChannelConfig
from src.config.settings import Settings


def _make_settings():
    return Settings(
        anthropic_api_key="x",
        elevenlabs_api_key="x",
        youtube_api_key="x",
        flux_api_key="x",
        kling_api_key="x",
    )


def _make_ctx(tmp_path, with_edit=True, with_thumbnail=True):
    channel = ChannelConfig(channel_id="ch", voice_id="v1", visual_style_presets={})
    ctx = PipelineContext(
        run_id="r1", run_dir=tmp_path, channel_name="test",
        channel=channel, urls=[], topic="test-topic",
    )
    ctx.script = ScriptResult(
        title="업로드 테스트",
        youtube_meta=YouTubeMeta(
            title="업로드 테스트",
            description="설명",
            tags=["태그1"],
        ),
    )
    if with_edit:
        (tmp_path / "final_shorts.mp4").write_bytes(b"fake-video")
        ctx.edit = EditResult(video_path="final_shorts.mp4")
    if with_thumbnail:
        (tmp_path / "thumbnail.png").write_bytes(b"fake-thumb")
        ctx.thumbnail = ThumbnailResult(image_path="thumbnail.png")
    return ctx


@pytest.mark.asyncio
async def test_sets_ctx_upload(tmp_path):
    ctx = _make_ctx(tmp_path)
    stage = UploadStage(settings=_make_settings())

    with patch("src.stages.upload.YouTubeUploadService") as MockSvc:
        svc_inst = MockSvc.return_value
        svc_inst.upload_video = MagicMock(return_value="vid123")
        svc_inst.upload_thumbnail = MagicMock()

        result = await stage.run(ctx)

    assert result.upload is not None
    assert result.upload.video_id == "vid123"
    assert "studio.youtube.com" in result.upload.studio_url
    assert "upload" in result.completed_stages


@pytest.mark.asyncio
async def test_raises_if_no_edit(tmp_path):
    ctx = _make_ctx(tmp_path, with_edit=False)
    stage = UploadStage(settings=_make_settings())
    with pytest.raises(ValueError, match="edit"):
        await stage.run(ctx)


@pytest.mark.asyncio
async def test_raises_if_no_thumbnail(tmp_path):
    ctx = _make_ctx(tmp_path, with_thumbnail=False)
    stage = UploadStage(settings=_make_settings())
    with pytest.raises(ValueError, match="thumbnail"):
        await stage.run(ctx)
