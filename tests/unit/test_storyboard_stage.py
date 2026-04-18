import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.config.channel import ChannelConfig
from src.config.settings import Settings
from src.pipeline.context import (
    BenchmarkResult,
    EnhancedScene,
    PipelineContext,
    Scene,
    ScriptResult,
    StoryboardResult,
    YouTubeMeta,
)
from src.stages.storyboard import StoryboardStage


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
    ctx.benchmark = BenchmarkResult(
        hook_pattern="질문형",
        story_structure="문제-해결",
        tone="교육적",
        pacing="빠름",
        visual_style="미니멀",
        strategy_summary="임팩트 있는 숏폼",
        recommended_duration=60,
    )
    ctx.script = ScriptResult(
        title="테스트 제목",
        hook="훅 문장",
        scenes=[
            Scene(scene_no=1, narration="나레이션 1", image_prompt="coffee cup", duration_sec=5, caption="cap1"),
            Scene(scene_no=2, narration="나레이션 2", image_prompt="brain neurons", duration_sec=5, caption="cap2"),
        ],
        cta="구독하세요",
        thumbnail_prompt="thumb",
        youtube_meta=YouTubeMeta(title="t", description="d", tags=[]),
    )
    return ctx


FAKE_STORYBOARD = StoryboardResult(
    scenes=[
        EnhancedScene(
            scene_no=1,
            enhanced_prompt="dark cinematic coffee cup dramatic lighting",
            negative_prompt="blurry, low quality",
        ),
        EnhancedScene(
            scene_no=2,
            enhanced_prompt="dark cinematic brain neurons glowing",
            negative_prompt="blurry, low quality",
        ),
    ],
    visual_style="dark cinematic",
)


@pytest.mark.asyncio
async def test_storyboard_stage_sets_ctx_storyboard(tmp_path):
    """StoryboardStage 실행 후 ctx.storyboard가 StoryboardResult로 채워진다"""
    settings = make_settings()
    stage = StoryboardStage(settings=settings)
    ctx = make_ctx(tmp_path)

    with patch("src.stages.storyboard.ClaudeService") as MockClaude:
        mock_claude = MockClaude.return_value
        mock_claude.enhance_storyboard = AsyncMock(return_value=FAKE_STORYBOARD)

        result = await stage.run(ctx)

    assert result.storyboard is not None
    assert isinstance(result.storyboard, StoryboardResult)
    assert len(result.storyboard.scenes) == 2
    assert result.storyboard.visual_style == "dark cinematic"


@pytest.mark.asyncio
async def test_storyboard_stage_passes_scenes_to_claude(tmp_path):
    """ClaudeService.enhance_storyboard에 씬 목록과 비주얼 스타일이 전달된다"""
    settings = make_settings()
    stage = StoryboardStage(settings=settings)
    ctx = make_ctx(tmp_path)

    with patch("src.stages.storyboard.ClaudeService") as MockClaude:
        mock_claude = MockClaude.return_value
        mock_claude.enhance_storyboard = AsyncMock(return_value=FAKE_STORYBOARD)

        await stage.run(ctx)

    call_kwargs = mock_claude.enhance_storyboard.call_args
    scenes_arg = call_kwargs[1].get("scenes") or call_kwargs[0][0]
    assert len(scenes_arg) == 2
    assert scenes_arg[0].image_prompt == "coffee cup"


@pytest.mark.asyncio
async def test_storyboard_stage_raises_if_no_script(tmp_path):
    """ctx.script가 None이면 ValueError를 발생시킨다"""
    settings = make_settings()
    stage = StoryboardStage(settings=settings)
    ctx = make_ctx(tmp_path)
    ctx.script = None

    with pytest.raises(ValueError, match="script"):
        await stage.run(ctx)
