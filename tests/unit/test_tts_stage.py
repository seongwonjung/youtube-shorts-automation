import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.config.channel import ChannelConfig
from src.config.settings import Settings
from src.pipeline.context import (
    PipelineContext,
    Scene,
    ScriptResult,
    SceneTTS,
    TTSResult,
    YouTubeMeta,
    BenchmarkResult,
)
from src.stages.tts import TTSStage


def make_settings() -> Settings:
    return Settings(
        anthropic_api_key="sk-test",
        elevenlabs_api_key="el-test",
        flux_api_key="flux-test",
        kling_api_key="kling-test",
        youtube_api_key="yt-test",
    )


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    ctx = PipelineContext(
        run_id="run1",
        run_dir=run_dir,
        channel_name="ch",
        channel=ChannelConfig(
            channel_id="ch",
            voice_id="voice-abc",
            visual_style_presets={"default": "dark cinematic"},
        ),
        urls=["https://youtube.com/watch?v=abc"],
        topic="카페인 부작용 5가지",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    ctx.script = ScriptResult(
        title="테스트 제목",
        hook="훅 문장",
        scenes=[
            Scene(scene_no=1, narration="나레이션 1", image_prompt="img1", duration_sec=5, caption="cap1"),
            Scene(scene_no=2, narration="나레이션 2", image_prompt="img2", duration_sec=5, caption="cap2"),
        ],
        cta="구독하세요",
        thumbnail_prompt="thumb",
        youtube_meta=YouTubeMeta(title="t", description="d", tags=[]),
    )
    return ctx


FAKE_TTS_SCENE = SceneTTS(
    scene_no=1,
    audio_path="tts/scene_1.mp3",
    srt_path="tts/scene_1.srt",
)


@pytest.mark.asyncio
async def test_tts_stage_sets_ctx_tts(tmp_path):
    """TTSStage 실행 후 ctx.tts가 TTSResult로 채워진다"""
    settings = make_settings()
    stage = TTSStage(settings=settings)
    ctx = make_ctx(tmp_path)

    fake_result = TTSResult(
        scenes=[
            SceneTTS(scene_no=1, audio_path="tts/scene_1.mp3", srt_path="tts/scene_1.srt"),
            SceneTTS(scene_no=2, audio_path="tts/scene_2.mp3", srt_path="tts/scene_2.srt"),
        ],
        voice_id="voice-abc",
    )

    with patch("src.stages.tts.ElevenLabsService") as MockEL:
        mock_el = MockEL.return_value
        mock_el.generate_scene_tts = AsyncMock(side_effect=[
            SceneTTS(scene_no=1, audio_path="tts/scene_1.mp3", srt_path="tts/scene_1.srt"),
            SceneTTS(scene_no=2, audio_path="tts/scene_2.mp3", srt_path="tts/scene_2.srt"),
        ])

        result = await stage.run(ctx)

    assert result.tts is not None
    assert isinstance(result.tts, TTSResult)
    assert len(result.tts.scenes) == 2
    assert result.tts.voice_id == "voice-abc"


@pytest.mark.asyncio
async def test_tts_stage_processes_scenes_sequentially(tmp_path):
    """TTSStage는 씬을 순서대로 처리하며 각 씬에 올바른 narration을 전달한다"""
    settings = make_settings()
    stage = TTSStage(settings=settings)
    ctx = make_ctx(tmp_path)

    with patch("src.stages.tts.ElevenLabsService") as MockEL:
        mock_el = MockEL.return_value
        mock_el.generate_scene_tts = AsyncMock(side_effect=[
            SceneTTS(scene_no=1, audio_path="tts/scene_1.mp3", srt_path="tts/scene_1.srt"),
            SceneTTS(scene_no=2, audio_path="tts/scene_2.mp3", srt_path="tts/scene_2.srt"),
        ])

        await stage.run(ctx)

    calls = mock_el.generate_scene_tts.call_args_list
    assert len(calls) == 2
    assert calls[0][1]["narration"] == "나레이션 1" or calls[0][0][1] == "나레이션 1"
    assert calls[1][1]["narration"] == "나레이션 2" or calls[1][0][1] == "나레이션 2"


@pytest.mark.asyncio
async def test_tts_stage_raises_if_no_script(tmp_path):
    """ctx.script가 None이면 ValueError를 발생시킨다"""
    settings = make_settings()
    stage = TTSStage(settings=settings)
    ctx = make_ctx(tmp_path)
    ctx.script = None

    with pytest.raises(ValueError, match="script"):
        await stage.run(ctx)
