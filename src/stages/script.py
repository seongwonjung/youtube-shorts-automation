from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings
from src.services.claude import ClaudeService


class ScriptStage(BaseStage):
    name = "script"
    stage_no = 2

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.benchmark is None:
            raise ValueError("benchmark 결과가 없습니다. BenchmarkStage를 먼저 실행하세요.")

        claude = ClaudeService(api_key=self.settings.anthropic_api_key)
        visual_style = ctx.channel.visual_style_presets.get("default", "")

        logger.info("[script] Claude 스크립트 생성 시작")
        ctx.script = await claude.generate_script(
            benchmark=ctx.benchmark,
            topic=ctx.topic,
            visual_style=visual_style,
            duration=ctx.duration,
        )
        logger.success(f"[script] 완료: {ctx.script.title}")
        return ctx
