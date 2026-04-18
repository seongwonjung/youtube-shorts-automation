from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings
from src.services.claude import ClaudeService


class StoryboardStage(BaseStage):
    name = "storyboard"
    stage_no = 4

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.script is None:
            raise ValueError("script 결과가 없습니다. ScriptStage를 먼저 실행하세요.")

        claude = ClaudeService(api_key=self.settings.anthropic_api_key)
        visual_style = ctx.channel.visual_style_presets.get("default", "")
        benchmark_style = ctx.benchmark.visual_style if ctx.benchmark else ""

        logger.info("[storyboard] Claude 스토리보드 강화 시작")
        ctx.storyboard = await claude.enhance_storyboard(
            scenes=ctx.script.scenes,
            visual_style=visual_style,
            benchmark_style=benchmark_style,
        )
        logger.success(f"[storyboard] 완료: {len(ctx.storyboard.scenes)}개 씬")
        return ctx
