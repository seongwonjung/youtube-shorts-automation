from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext, ThumbnailResult
from src.config.settings import Settings
from src.services.flux import FluxService


class ThumbnailStage(BaseStage):
    name = "thumbnail"
    stage_no = 7

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.script is None:
            raise ValueError("script 결과가 없습니다. ScriptStage를 먼저 실행하세요.")

        flux = FluxService(api_key=self.settings.flux_api_key)
        prompt = ctx.script.thumbnail_prompt or ctx.script.title or ctx.topic

        logger.info(f"[thumbnail] 썸네일 생성 중 (prompt: {prompt[:50]}...)")
        image_path = await flux.generate_thumbnail(
            prompt=prompt,
            run_dir=ctx.run_dir,
        )

        ctx.thumbnail = ThumbnailResult(image_path=image_path)
        ctx.completed_stages.append(self.name)
        logger.info(f"[thumbnail] 완료: {image_path}")
        return ctx
