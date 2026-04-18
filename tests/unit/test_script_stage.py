import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.config.channel import ChannelConfig
from src.config.settings import Settings
from src.pipeline.context import (
    BenchmarkResult,
    PipelineContext,
    Scene,
    ScriptResult,
    YouTubeMeta,
)
from src.stages.script import ScriptStage


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
            voice_id="v",
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
    return ctx


FAKE_SCRIPT = ScriptResult(
    title="카페인 과다 섭취 부작용 5가지",
    hook="하루에 커피 몇 잔 마시세요?",
    scenes=[
        Scene(
            scene_no=1,
            narration="카페인은 우리 몸에 어떤 영향을 줄까요?",
            image_prompt="coffee cup closeup dramatic",
            duration_sec=5,
            caption="카페인의 진실",
        )
    ],
    cta="구독하고 더 알아보세요",
    thumbnail_prompt="coffee with warning sign",
    youtube_meta=YouTubeMeta(
        title="카페인 부작용",
        description="카페인에 대해 알아보세요",
        tags=["카페인", "건강"],
    ),
)


@pytest.mark.asyncio
async def test_script_stage_sets_ctx_script(tmp_path):
    """ScriptStage 실행 후 ctx.script가 ScriptResult로 채워진다"""
    settings = make_settings()
    stage = ScriptStage(settings=settings)
    ctx = make_ctx(tmp_path)

    with patch("src.stages.script.ClaudeService") as MockClaude:
        mock_claude = MockClaude.return_value
        mock_claude.generate_script = AsyncMock(return_value=FAKE_SCRIPT)

        result = await stage.run(ctx)

    assert result.script is not None
    assert isinstance(result.script, ScriptResult)
    assert result.script.hook == "하루에 커피 몇 잔 마시세요?"


@pytest.mark.asyncio
async def test_script_stage_passes_benchmark_to_claude(tmp_path):
    """ctx.benchmark가 ClaudeService.generate_script에 전달된다"""
    settings = make_settings()
    stage = ScriptStage(settings=settings)
    ctx = make_ctx(tmp_path)

    with patch("src.stages.script.ClaudeService") as MockClaude:
        mock_claude = MockClaude.return_value
        mock_claude.generate_script = AsyncMock(return_value=FAKE_SCRIPT)

        await stage.run(ctx)

    call_kwargs = mock_claude.generate_script.call_args
    benchmark_arg = call_kwargs[1].get("benchmark") or call_kwargs[0][0]
    assert benchmark_arg.hook_pattern == "질문형"


@pytest.mark.asyncio
async def test_script_stage_raises_if_no_benchmark(tmp_path):
    """ctx.benchmark가 None이면 ValueError를 발생시킨다"""
    settings = make_settings()
    stage = ScriptStage(settings=settings)
    ctx = make_ctx(tmp_path)
    ctx.benchmark = None

    with pytest.raises(ValueError, match="benchmark"):
        await stage.run(ctx)
