from abc import ABC, abstractmethod
from src.pipeline.context import PipelineContext


class BaseStage(ABC):
    name: str
    stage_no: int

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """스테이지 실행. ctx를 받아 결과를 채워 반환."""
        ...

    def can_skip(self, ctx: PipelineContext) -> bool:
        """completed_stages에 이미 있으면 True."""
        return self.name in ctx.completed_stages
