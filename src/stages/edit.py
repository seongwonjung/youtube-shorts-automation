from loguru import logger
from src.stages.base import BaseStage
from src.pipeline.context import PipelineContext
from src.config.settings import Settings


class EditStage(BaseStage):
    name = "edit"
    stage_no = 6

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.warning(f"[{self.name}] 스텁 — Plan 4에서 구현 예정")
        return ctx
