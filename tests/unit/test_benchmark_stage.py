import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.config.channel import ChannelConfig
from src.config.settings import Settings
from src.pipeline.context import BenchmarkResult, PipelineContext
from src.stages.benchmark import BenchmarkStage


def make_settings(**kwargs) -> Settings:
    defaults = {
        "anthropic_api_key": "sk-test",
        "elevenlabs_api_key": "el-test",
        "flux_api_key": "flux-test",
        "kling_api_key": "kling-test",
        "youtube_api_key": "yt-test",
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def make_ctx(tmp_path: Path) -> PipelineContext:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    return PipelineContext(
        run_id="run1",
        run_dir=run_dir,
        channel_name="ch",
        channel=ChannelConfig(channel_id="ch", voice_id="v"),
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        topic="카페인 부작용",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


FAKE_BENCHMARK = BenchmarkResult(
    hook_pattern="질문형",
    story_structure="문제-해결",
    tone="교육적",
    pacing="빠름",
    visual_style="미니멀",
    strategy_summary="짧고 임팩트 있는 영상",
    recommended_duration=60,
)


@pytest.mark.asyncio
async def test_benchmark_stage_sets_ctx_benchmark(tmp_path):
    """BenchmarkStage 실행 후 ctx.benchmark가 BenchmarkResult로 채워진다"""
    settings = make_settings()
    stage = BenchmarkStage(settings=settings)
    ctx = make_ctx(tmp_path)

    with (
        patch("src.stages.benchmark.YouTubeService") as MockYT,
        patch("src.stages.benchmark.ClaudeService") as MockClaude,
    ):
        mock_yt = MockYT.return_value
        mock_yt.fetch_video_data = AsyncMock(return_value={
            "video_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "desc",
            "view_count": 1000,
            "like_count": 100,
            "comments": ["great video"],
            "transcript": "hello world",
        })

        mock_claude = MockClaude.return_value
        mock_claude.analyze_benchmark = AsyncMock(return_value=FAKE_BENCHMARK)

        result = await stage.run(ctx)

    assert result.benchmark is not None
    assert isinstance(result.benchmark, BenchmarkResult)
    assert result.benchmark.hook_pattern == "질문형"


@pytest.mark.asyncio
async def test_benchmark_stage_fetches_each_url(tmp_path):
    """urls 목록의 각 URL에 대해 YouTubeService.fetch_video_data가 호출된다"""
    settings = make_settings()
    stage = BenchmarkStage(settings=settings)
    ctx = make_ctx(tmp_path)
    ctx.urls = [
        "https://www.youtube.com/watch?v=aaa",
        "https://www.youtube.com/watch?v=bbb",
    ]

    with (
        patch("src.stages.benchmark.YouTubeService") as MockYT,
        patch("src.stages.benchmark.ClaudeService") as MockClaude,
    ):
        mock_yt = MockYT.return_value
        mock_yt.fetch_video_data = AsyncMock(return_value={
            "video_id": "aaa",
            "title": "T",
            "description": "",
            "view_count": 0,
            "like_count": 0,
            "comments": [],
            "transcript": "",
        })
        mock_claude = MockClaude.return_value
        mock_claude.analyze_benchmark = AsyncMock(return_value=FAKE_BENCHMARK)

        await stage.run(ctx)

    assert mock_yt.fetch_video_data.call_count == 2


@pytest.mark.asyncio
async def test_benchmark_stage_passes_youtube_data_to_claude(tmp_path):
    """YouTubeService에서 수집한 데이터가 ClaudeService.analyze_benchmark에 전달된다"""
    settings = make_settings()
    stage = BenchmarkStage(settings=settings)
    ctx = make_ctx(tmp_path)

    video_data = {
        "video_id": "dQw4w9WgXcQ",
        "title": "Coffee Overdose",
        "description": "side effects",
        "view_count": 500000,
        "like_count": 20000,
        "comments": ["scary", "helpful"],
        "transcript": "caffeine is dangerous",
    }

    with (
        patch("src.stages.benchmark.YouTubeService") as MockYT,
        patch("src.stages.benchmark.ClaudeService") as MockClaude,
    ):
        mock_yt = MockYT.return_value
        mock_yt.fetch_video_data = AsyncMock(return_value=video_data)
        mock_claude = MockClaude.return_value
        mock_claude.analyze_benchmark = AsyncMock(return_value=FAKE_BENCHMARK)

        await stage.run(ctx)

    call_args = mock_claude.analyze_benchmark.call_args
    videos_arg = call_args[0][0]
    assert any(v["title"] == "Coffee Overdose" for v in videos_arg)
