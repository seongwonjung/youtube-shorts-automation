from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings
from src.services.youtube import YouTubeService
from src.services.claude import ClaudeService


class BenchmarkStage(BaseStage):
    name = "benchmark"
    stage_no = 1

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        yt = YouTubeService(api_key=self.settings.youtube_api_key)
        claude = ClaudeService(api_key=self.settings.anthropic_api_key)

        videos = []
        for url in ctx.urls:
            logger.info(f"[benchmark] 영상 수집: {url}")
            data = await yt.fetch_video_data(url)
            videos.append(data)

        logger.info("[benchmark] Claude 분석 시작")
        ctx.benchmark = await claude.analyze_benchmark(videos)
        logger.success(f"[benchmark] 완료: {ctx.benchmark.strategy_summary[:50]}")
        return ctx
